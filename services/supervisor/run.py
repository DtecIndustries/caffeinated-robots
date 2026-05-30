"""Run both loops together: the ticket monitor and the supervisor assistant."""
import asyncio

import monitor
import supervisor_agent


async def main():
    await asyncio.gather(monitor.run(), supervisor_agent.run())


if __name__ == "__main__":
    asyncio.run(main())
