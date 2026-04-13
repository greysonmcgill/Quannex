#!/usr/bin/env python3
"""
Run full-scale universe simulation with 500 agents and 100K accounts.
"""

import asyncio

from quan.simulation.full_scale_simulation import run_full_scale_simulation

if __name__ == "__main__":
    asyncio.run(run_full_scale_simulation())
