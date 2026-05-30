"""Loop A — watch the faulty_parts table and file a Discord ticket per new fault.

A new row in faulty_parts (status='open') is a defect the QC/vision pipeline
detected. We post it to Discord and mark it 'ticketed'. If the row carries a
photo (base64 in image_b64), we upload it as a Discord attachment so the
supervisor can eyeball the fault. The supervisor then resolves it via Discord
(see supervisor_agent.py), which the robot code reads.

The photo is read in chunks: the Soda Straw execute_query tool truncates cells
at ~4000 chars, so a full camera-frame base64 (often 5-10 KB) would arrive
corrupted in a single SELECT. We fetch it via substring() in <4000-char pieces
and reassemble — keeping everything through the governed straw.
"""
import asyncio
import base64
import json

import httpx

import sodastraw as straw
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID, MONITOR_INTERVAL

DISCORD_API = "https://discord.com/api/v10"
CHUNK = 3900  # stay safely under the straw's ~4000-char cell truncation

OPEN_FAULTS_SQL = """
SELECT id, station_pos, fault, confidence
FROM faulty_parts
WHERE status = 'open'
ORDER BY detected_at ASC
"""

MARK_TICKETED_SQL = """
UPDATE faulty_parts
SET status = 'ticketed', discord_message_id = :mid
WHERE id = :id
"""


def _embed(f):
    station = f.get("station_pos")
    fields = [
        {"name": "Fault", "value": str(f.get("fault") or "?"), "inline": True},
        {"name": "Station", "value": str(station) if station is not None else "—", "inline": True},
    ]
    if f.get("confidence") is not None:
        fields.append({"name": "Confidence", "value": f"{f['confidence']:.2f}", "inline": True})
    return {
        "title": f"🚧 Ticket #{f['id']} — {f.get('fault') or 'fault detected'}",
        "color": 15158332,
        "fields": fields,
        "footer": {"text": "Reply GO (let it continue) or NO-GO (pull it off the line), with a reason."},
    }


async def _fetch_image_b64(fault_id):
    """Read image_b64 in <4000-char chunks (the straw truncates larger cells)."""
    meta = await straw.sql(
        "SELECT length(image_b64) AS n FROM faulty_parts WHERE id = :id",
        intent=f"Get photo length for faulty part {fault_id}", params={"id": fault_id})
    n = (meta[0]["n"] if meta else None) or 0
    if n == 0:
        return None
    parts = []
    off = 1
    while off <= n:
        rows = await straw.sql(
            "SELECT substring(image_b64 FROM :off FOR :len) AS chunk FROM faulty_parts WHERE id = :id",
            intent=f"Fetch photo chunk for faulty part {fault_id}",
            params={"off": off, "len": CHUNK, "id": fault_id})
        parts.append((rows[0]["chunk"] if rows else "") or "")
        off += CHUNK
    return "".join(parts)


def _decode_image(value):
    """If the value is base64 (not an http URL), decode to (bytes, filename, mime)."""
    if not value or value.startswith("http"):
        return None
    data = value.split(",", 1)[-1] if value.startswith("data:") else value
    try:
        raw = base64.b64decode(data, validate=False)
    except Exception:
        return None
    if len(raw) < 8:
        return None
    if raw[:3] == b"\xff\xd8\xff":
        return raw, "photo.jpg", "image/jpeg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return raw, "photo.png", "image/png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return raw, "photo.webp", "image/webp"
    if raw[:3] == b"GIF":
        return raw, "photo.gif", "image/gif"
    return raw, "photo.png", "image/png"  # default; Discord sniffs the real type


async def _post_with_photo(embed, raw, filename, mime):
    """Upload the photo as a Discord attachment (multipart) alongside the embed.

    This one call goes straight to Discord (not through the straw) because the
    Soda Straw http_request tool only sends JSON bodies, not binary multipart.
    """
    embed = {**embed, "image": {"url": f"attachment://{filename}"}}
    payload = {"embeds": [embed], "attachments": [{"id": 0, "filename": filename}]}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{DISCORD_API}/channels/{DISCORD_CHANNEL_ID}/messages",
            headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
            data={"payload_json": json.dumps(payload)},
            files={"files[0]": (filename, raw, mime)},
        )
        r.raise_for_status()
        return r.json()


async def _post_via_straw(embed, image_value):
    if (image_value or "").startswith("http"):
        embed = {**embed, "image": {"url": image_value}}
    resp = await straw.discord(
        "POST", f"/channels/{DISCORD_CHANNEL_ID}/messages",
        intent="Post a faulty-part ticket to Discord", body={"embeds": [embed]})
    return (resp or {}).get("body") or {}


async def file_ticket(f):
    embed = _embed(f)
    b64 = await _fetch_image_b64(f["id"])
    img = _decode_image(b64)
    if img and DISCORD_BOT_TOKEN:
        raw, filename, mime = img
        msg = await _post_with_photo(embed, raw, filename, mime)
    else:
        if img and not DISCORD_BOT_TOKEN:
            print("[monitor] photo present but DISCORD_BOT_TOKEN not set — posting ticket without it")
        msg = await _post_via_straw(embed, b64)

    message_id = msg.get("id")
    await straw.sql(
        MARK_TICKETED_SQL,
        intent=f"Mark faulty part #{f['id']} as ticketed",
        params={"mid": str(message_id) if message_id else None, "id": f["id"]},
    )
    print(f"[monitor] ticketed faulty part #{f['id']} ({f.get('fault')}) -> discord msg {message_id}")


async def tick():
    faults = await straw.sql(OPEN_FAULTS_SQL, intent="Scan faulty_parts for new open faults")
    for f in faults:
        try:
            await file_ticket(f)
        except Exception as e:  # one bad ticket shouldn't kill the loop
            print(f"[monitor] failed to ticket faulty part #{f.get('id')}: {e}")


async def run():
    print("[monitor] watching faulty_parts for new faults...")
    while True:
        try:
            await tick()
        except Exception as e:
            print(f"[monitor] tick error: {e}")
        await asyncio.sleep(MONITOR_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run())
