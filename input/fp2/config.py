"""Load and validate config/fp2_zones.json."""

import json
import pathlib
from dataclasses import dataclass, field

from .steering import ZONE_NAMES

DEFAULT_PATH = pathlib.Path("config/fp2_zones.json")

#: Written by `pair_fp2.py`. Never commit it.
DEFAULT_PAIRING_FILE = pathlib.Path.home() / ".local/share/aiohomekit/pairing.json"


class ConfigError(Exception):
    """Raised with a message meant for the person running the game."""


@dataclass
class Fp2Config:
    alias: str = "fp2"
    zones: dict = field(default_factory=dict)
    debounce_ms: int = 150
    lost_grace_ms: int = 1000
    pairing_file: pathlib.Path = DEFAULT_PAIRING_FILE

    @property
    def char_cache_file(self):
        return self.pairing_file.parent / "charmap.json"

    def subscriptions(self):
        """The zone ids as aiohomekit (aid, iid) pairs."""
        return [_split_key(key) for key in self.zones.values()]


def _split_key(key):
    aid, _, iid = str(key).partition(".")
    if not aid.isdigit() or not iid.isdigit():
        raise ConfigError(
            f"zone id {key!r} is not in 'aid.iid' form (e.g. '1.13'). "
            "Run `python -m input.fp2 identify` and copy the ids it prints.")
    return int(aid), int(iid)


def load(path=DEFAULT_PATH):
    path = pathlib.Path(path)
    if not path.exists():
        raise ConfigError(f"{path} not found. Copy the sample from the README "
                          "and fill in the zone ids from `identify`.")
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc}") from exc
    return parse(raw, source=path)


def parse(raw, source="config"):
    """Validate a config dict. Every failure names what to fix."""
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: expected a JSON object at the top level")

    zones = raw.get("zones")
    if not isinstance(zones, dict):
        raise ConfigError(f'{source}: missing a "zones" object')

    missing = [name for name in ZONE_NAMES if name not in zones]
    if missing:
        raise ConfigError(
            f"{source}: zones is missing {', '.join(missing)}. "
            f"All five of {', '.join(ZONE_NAMES)} are required.")

    unknown = sorted(set(zones) - set(ZONE_NAMES))
    if unknown:
        raise ConfigError(f"{source}: unknown zone name(s) {', '.join(unknown)}. "
                          f"Expected only {', '.join(ZONE_NAMES)}.")

    seen = {}
    for name in ZONE_NAMES:
        key = str(zones[name])
        _split_key(key)
        if key in seen:
            raise ConfigError(
                f"{source}: zones {seen[key]} and {name} both use id {key}. "
                "Each zone needs its own sensor; re-run `identify`.")
        seen[key] = name

    config = Fp2Config(alias=str(raw.get("alias", "fp2")),
                       zones={name: str(zones[name]) for name in ZONE_NAMES})
    for field_name in ("debounce_ms", "lost_grace_ms"):
        value = raw.get(field_name, getattr(config, field_name))
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise ConfigError(f"{source}: {field_name} must be a number of "
                              f"milliseconds, got {value!r}")
        setattr(config, field_name, value)

    if "pairing_file" in raw:
        config.pairing_file = pathlib.Path(raw["pairing_file"]).expanduser()
    return config
