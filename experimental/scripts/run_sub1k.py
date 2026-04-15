#!/usr/bin/env python3
"""
Run sub-$1K micro-debt collection simulation.
QUAN's targeted sweet spot - accounts large agencies ignore.
"""

import asyncio

from quan.simulation.sub_1k_simulation import run_sub1k_simulation

if __name__ == "__main__":
    asyncio.run(run_sub1k_simulation())
