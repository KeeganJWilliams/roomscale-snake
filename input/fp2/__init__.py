"""Aqara FP2 input: floor zones -> debounced steering commands.

Importing this package does not import aiohomekit; only client.py does,
and the adapter loads it lazily when it actually starts a connection.
"""

from .adapter import Fp2Input
from .config import ConfigError, Fp2Config
from .config import load as load_config
from .steering import ZONE_NAMES, Steering, ZoneEvent

__all__ = ["ConfigError", "Fp2Config", "Fp2Input", "Steering", "ZONE_NAMES",
           "ZoneEvent", "load_config"]
