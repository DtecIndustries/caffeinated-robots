"""Loop B — the supervisor assistant living in the Discord ticket channel.

Polls the channel for new human messages. For each one, Claude reads faulty-part
context from Postgres (read-only query_db tool), answers questions, and — when the
supervisor gives a clear GO / NO-GO instruction — records it on the faulty_parts
row (set_resolution tool). The robot code reads that resolution and acts.
"""
import asyncio
import json

from anthropic import AsyncAnthropic

import sodastraw as straw
from config import (ANTHROPIC_EFFORT, ANTHROPIC_MODEL, DISCORD_BOT_USER_ID,
                    DISCORD_CHANNEL_ID, DISCORD_POLL_INTERVAL, STATE_FILE)

client = AsyncAnthropic()

SYSTEM_PROMPT = """You are the production-line supervisor assistant for "Caffeinated Robots", \
operating inside a Discord channel. Each ticket is a faulty part the QC/vision pipeline flagged on \
the line. The supervisor decides GO or NO-GO, and the robot reads that decision and acts.

Table `faulty_parts` (database caffeinated, public schema):
- id, detected_at, station_pos, fault (text, e.g. "bad paint"), confidence, image_url
- status: open -> ticketed -> resolved
- resolution (NULL until you set it): 'go' or 'no_go'
- resolution_note, resolved_by, resolved_at, robot_acked (the robot sets this true once it acts)

GO vs NO-GO — this is exactly what the robot acts on:
- 'go'    = the part is fine and may continue on the line (e.g. a false positive). The robot lets it pass.
- 'no_go' = the part is genuinely faulty and must NOT continue — the robot pulls it off the line for \
rework / repackaging / scrap. Put the follow-up (rework, scrap, ...) in the note.

Your job:
- Answer the supervisor's questions about a faulty part concisely, in plain Discord text (short). \
Use query_db to look up facts first.
- When the supervisor gives a clear instruction, call set_resolution:
  * "go" / "pass" / "let it through" / "it's fine" / "false positive" / "doorlaten"  -> resolution="go"
  * "no-go" / "reject" / "scrap" / "rework" / "pull it" / "herverpakken" / "eruit"    -> resolution="no_go"
- Be careful: a word like "accept" is ambiguous. If the supervisor's instruction seems to conflict with \
the fault (e.g. sounds positive while the part is clearly damaged), ask one short clarifying question \
instead of guessing.
- If it is ambiguous which faulty part the supervisor means, ask one short clarifying question. Never \
invent an id — use the open tickets list or query_db.
- After setting a resolution, confirm in one sentence: for GO say the robot lets the part continue; for \
NO-GO say the robot pulls the part off the line (mention rework / repack if the supervisor asked)."""

QUERY_TOOL = {
    "name": "query_db",
    "description": "Run a read-only SQL SELECT against the caffeinated database and return rows as JSON.",
    "input_schema": {
        "type": "object",
        "properties": {"sql": {"type": "string", "description": "A single SELECT or WITH statement."}},
        "required": ["sql"],
    },
}

RESOLUTION_TOOL = {
    "name": "set_resolution",
    "description": ("Record the supervisor's GO / NO-GO decision so the robot can act: 'go' = let the part "
                    "continue, 'no_go' = pull it off the line. Sets resolution + note and marks it resolved."),
    "input_schema": {
        "type": "object",
        "properties": {
            "faulty_part_id": {"type": "integer"},
            "resolution": {"type": "string", "enum": ["go", "no_go"]},
            "note": {"type": "string",
                     "description": "Short reason / follow-up (e.g. 'false positive', 'rework', 'scrap'), "
                                    "quoting the supervisor."},
        },
        "required": ["faulty_part_id", "resolution"],
    },
}


async def _query_db(sql):
    head = sql.lstrip().lower()
    if not (head.startswith("select") or head.startswith("with")):
        return "Only SELECT/WITH queries are allowed here."
    rows = await straw.sql(sql, intent="Supervisor assistant answering a question about a faulty part")
    return json.dumps(rows, default=str)[:6000]


async def _set_resolution(faulty_part_id, resolution, operator, note):
    await straw.sql(
        "UPDATE faulty_parts "
        "SET resolution = :res, resolution_note = :note, resolved_by = :op, "
        "    resolved_at = now(), status = 'resolved' "
        "WHERE id = :id",
        intent=f"Record supervisor {resolution} decision for faulty part {faulty_part_id}",
        params={"res": resolution, "note": note or "", "op": operator, "id": faulty_part_id},
    )
    action = "let the part continue" if resolution == "go" else "pull the part off the line"
    return f"{resolution.upper()} recorded for faulty part #{faulty_part_id}; the robot will {action}."


async def _open_tickets():
    return await straw.sql(
        "SELECT id AS ticket, station_pos, fault, confidence, status, "
        "discord_message_id AS message_id "
        "FROM faulty_parts WHERE resolution IS NULL ORDER BY detected_at DESC",
        intent="List unresolved faulty parts as context for the supervisor assistant",
    )


async def handle_message(msg):
    author = msg.get("author") or {}
    operator = author.get("global_name") or author.get("username") or "supervisor"
    tickets = await _open_tickets()

    context = (
        f"Open tickets right now:\n{json.dumps(tickets, default=str)}\n\n"
        f"Supervisor **{operator}** said:\n{msg.get('content', '')}"
    )
    ref = msg.get("message_reference") or {}
    if ref.get("message_id"):
        context += (f"\n\n(This is a reply to Discord message id {ref['message_id']} — "
                    f"match it against a ticket's message_id above.)")

    messages = [{"role": "user", "content": context}]
    final_text = ""
    for _ in range(8):  # bound the tool loop
        resp = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            thinking={"type": "adaptive"},
            output_config={"effort": ANTHROPIC_EFFORT},
            tools=[QUERY_TOOL, RESOLUTION_TOOL],
            messages=messages,
        )
        final_text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if resp.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            try:
                if b.name == "query_db":
                    out = await _query_db(b.input["sql"])
                elif b.name == "set_resolution":
                    out = await _set_resolution(
                        b.input["faulty_part_id"], b.input["resolution"], operator,
                        b.input.get("note", ""))
                else:
                    out = f"Unknown tool {b.name}"
            except Exception as e:
                out = f"Error: {e}"
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": str(out)})
        messages.append({"role": "user", "content": results})

    if final_text:
        await straw.discord(
            "POST", f"/channels/{DISCORD_CHANNEL_ID}/messages",
            intent="Supervisor assistant replying in Discord",
            body={"content": final_text[:1900], "message_reference": {"message_id": msg["id"]}},
        )
        print(f"[supervisor] replied to {operator}: {final_text[:80]}")


def _load_last_id():
    try:
        with open(STATE_FILE) as f:
            return json.load(f).get("last_id")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_last_id(last_id):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_id": last_id}, f)


async def _newest_id():
    resp = await straw.discord(
        "GET", f"/channels/{DISCORD_CHANNEL_ID}/messages",
        intent="Get latest message id to start watching from", query={"limit": "1"})
    body = (resp or {}).get("body") or []
    return body[0]["id"] if body else None


async def run():
    last_id = _load_last_id() or await _newest_id()
    print(f"[supervisor] listening in channel {DISCORD_CHANNEL_ID} from message {last_id}")
    while True:
        try:
            query = {"limit": "50"}
            if last_id:
                query["after"] = str(last_id)
            resp = await straw.discord(
                "GET", f"/channels/{DISCORD_CHANNEL_ID}/messages",
                intent="Poll channel for new supervisor messages", query=query)
            new = (resp or {}).get("body") or []
            for msg in reversed(new):  # Discord returns newest-first; process oldest-first
                last_id = msg["id"]
                author = msg.get("author") or {}
                if author.get("bot") or str(author.get("id")) == str(DISCORD_BOT_USER_ID):
                    continue  # ignore our own messages and other bots
                if not (msg.get("content") or "").strip():
                    continue
                try:
                    await handle_message(msg)
                except Exception as e:
                    print(f"[supervisor] error handling message {msg.get('id')}: {e}")
            if new:
                _save_last_id(last_id)
        except Exception as e:
            print(f"[supervisor] poll error: {e}")
        await asyncio.sleep(DISCORD_POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run())
