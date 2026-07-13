"""Pytest configuration for the VinAMI ACS scaffold."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for location in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    sys.path.insert(0, str(location))
