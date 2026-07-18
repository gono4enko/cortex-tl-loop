#!/usr/bin/env python3
"""TL Orchestration Loop — PM2 entrypoint."""
import asyncio, logging, os, sys
from pathlib import Path

sys.path.insert(0, "/home/hermes")
from dotenv import load_dotenv
load_dotenv(Path("/home/hermes/cortex/.env"))

from cortex.tl_loop.loop import run_forever

INTERVAL = int(os.environ.get("TL_LOOP_INTERVAL", "300"))
COST_LIMIT = float(os.environ.get("DAILY_COST_LIMIT_USD", "20"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [tl-loop] %(levelname)s: %(message)s",
)
logger = logging.getLogger("tl_loop")

async def main():
    logger.info(f"TL Orchestration Loop v1.0 — interval={INTERVAL}s, cost_limit=${COST_LIMIT}")
    await run_forever(INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
