"""Used-car inventory and refurbishment flow simulator (synthetic, assumption-based)."""
from .config import Params, SEGMENTS, load_network, ASSUMPTIONS
from .engine import run, simulate_once
__all__ = ["Params", "SEGMENTS", "load_network", "ASSUMPTIONS", "run", "simulate_once"]
