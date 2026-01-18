#!/usr/bin/env python3
"""
Run perpetual collection simulation with maximum agent deployment.
"""

import asyncio
import sys
sys.path.insert(0, '/home/user/Quan')

from quan.simulation.perpetual_simulation import run_maximum_deployment

if __name__ == "__main__":
    asyncio.run(run_maximum_deployment())
