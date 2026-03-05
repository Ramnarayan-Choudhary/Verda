"""Shared test fixtures."""

import sys
from pathlib import Path

# Ensure hypo-claude and shared are importable
root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "hypo-claude"))
