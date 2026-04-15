#!/usr/bin/env python3
"""
Run perpetual collection simulation with maximum agent deployment.
"""

import asyncio

from quan.simulation.perpetual_simulation import run_maximum_deployment

if __name__ == "__main__":
    asyncio.run(run_maximum_deployment())
