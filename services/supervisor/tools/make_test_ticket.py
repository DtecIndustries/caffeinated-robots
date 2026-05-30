"""Insert a fake faulty part so you can watch a ticket appear in Discord.

    python tools/make_test_ticket.py

Run from services/supervisor/ (so config.py / sodastraw.py import cleanly), or
with that directory on PYTHONPATH.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sodastraw as straw  # noqa: E402

# A 1x1 transparent PNG, base64 — stand-in for a real camera frame.
SAMPLE_IMAGE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


async def main():
    rows = await straw.sql(
        "INSERT INTO faulty_parts (station_pos, fault, confidence, image_url) "
        "VALUES (:pos, :fault, :conf, :img) RETURNING id",
        intent="Create a demo faulty part to trigger a Discord ticket",
        params={"pos": 3, "fault": "bad paint", "conf": 0.92, "img": SAMPLE_IMAGE_B64},
    )
    fid = rows[0]["id"]
    print(f"Created faulty part #{fid} (fault='bad paint', status='open').")
    print("The monitor should post a ticket to Discord within a few seconds.")


if __name__ == "__main__":
    asyncio.run(main())
