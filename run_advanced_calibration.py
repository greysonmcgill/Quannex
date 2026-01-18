#!/usr/bin/env python3
"""
Run advanced model calibration to optimize recovery, efficiency, and risk.
"""

import asyncio
import sys
sys.path.insert(0, '/home/user/Quan')

from quan.simulation.calibration_engine import run_calibration

if __name__ == "__main__":
    asyncio.run(run_calibration())
