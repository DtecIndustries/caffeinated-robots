"""Loop A — watch the faulty_parts table and file a Discord ticket per new fault.

A new row in faulty_parts (status='open') is a defect the QC/vision pipeline
detected. We post it to Discord and mark it 'ticketed'. The supervisor then adds
a resolution via Discord (see supervisor_agent.py), which the robot code reads.
"""
import asyncio

import sodastraw as straw
from config import DISCORD_CHANNEL_ID, MONITOR_INTERVAL

OPEN_FAULTS_SQL = """
SELECT id, station_pos, fault, confidence, image_url
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
    embed = {
        "title": f"🚧 Ticket #{f['id']} — {f.get('fault') or 'fault detected'}",
        "color": 15158332,
        "fields": fields,
        "footer": {"text": "Reply GO (let it continue) or NO-GO (pull it off the line), with a reason."},
    }
    # image_url holds base64 by default, which Discord can't render — only set the
    # embed image when it's a real http(s) URL.
    if (f.get("image_url") or "").startswith("http"):
        embed["image"] = {"url": f["image_url"]}
    return embed


async def file_ticket(f):
    resp = await straw.discord(
        "POST", f"/channels/{DISCORD_CHANNEL_ID}/messages",
        intent=f"Post ticket for faulty part #{f['id']} to Discord",
        body={"embeds": [_embed(f)]},
    )
    message_id = ((resp or {}).get("body") or {}).get("id")
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
