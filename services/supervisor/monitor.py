"""Loop A — watch the faulty_parts table and file a Discord ticket per new fault.

A new row in faulty_parts (status='open') is a defect the QC/vision pipeline
detected. We post it to Discord and mark it 'ticketed'. If the row carries a
photo (base64 in image_b64), we upload it as a Discord attachment so the
supervisor can eyeball the fault. The supervisor then resolves it via Discord
(see supervisor_agent.py), which the robot code reads.
"""
import asyncio
import base64
import json

import httpx

import sodastraw as straw
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID, MONITOR_INTERVAL

DISCORD_API = "https://discord.com/api/v10"

OPEN_FAULTS_SQL = """
SELECT id, station_pos, fault, confidence, image_b64
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


def _decode_image(value):
    """If image_b64 holds base64 (not an http URL), decode to (bytes, filename, mime)."""
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


async def _post_via_straw(embed, image_b64):
    if (image_b64 or "").startswith("http"):
        embed = {**embed, "image": {"url": image_b64}}
    resp = await straw.discord(
        "POST", f"/channels/{DISCORD_CHANNEL_ID}/messages",
        intent="Post a faulty-part ticket to Discord", body={"embeds": [embed]})
    return (resp or {}).get("body") or {}


async def file_ticket(f):
    embed = _embed(f)
    img = _decode_image(f.get("image_b64"))
    if img and DISCORD_BOT_TOKEN:
        raw, filename, mime = img
        msg = await _post_with_photo(embed, raw, filename, mime)
    else:
        if img and not DISCORD_BOT_TOKEN:
            print("[monitor] photo present but DISCORD_BOT_TOKEN not set — posting ticket without it")
        msg = await _post_via_straw(embed, f.get("image_b64"))

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
