"""FP2 command line: python -m input.fp2 list | identify | run

    list      every occupancy sensor the FP2 exposes, as aid.iid + name
    identify  stream zone changes; walk each zone and note which id lights
              up, then put those ids in config/fp2_zones.json
    run       the real steering output, using the ids already in the config

Add --fake <script> to identify or run to replay a scripted event file
instead of talking to the sensor.
"""

import argparse
import asyncio
import logging
import sys
import threading
import time

from .config import ConfigError
from .config import DEFAULT_PATH, load

POLL_S = 0.01


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m input.fp2", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("list", "identify", "run"))
    parser.add_argument("--config", default=DEFAULT_PATH,
                        help=f"zone config (default {DEFAULT_PATH})")
    parser.add_argument("--fake", metavar="SCRIPT",
                        help="replay a scripted event file instead of the sensor")
    parser.add_argument("--telemetry", action="store_true",
                        help="also write the Telemetry CSV (run mode)")
    return parser.parse_args(argv)


def make_client_factory(fake_script):
    if fake_script is None:
        from .adapter import default_client_factory

        return default_client_factory

    from .fake import FakeClient

    def factory(config, on_event, on_status):
        return FakeClient(config, on_event, on_status, script_path=fake_script)

    return factory


def cmd_list(config):
    from .client import Fp2Client

    zones = asyncio.run(Fp2Client(config, lambda event: None).list_zones())
    if not zones:
        print("No occupancy sensors found. Are the zones drawn in the Aqara app?")
        return 1
    print(f"{'aid.iid':>8}  name")
    for key, name in zones:
        print(f"{key:>8}  {name}")
    print("\nOne of these covers the whole detection area rather than a drawn "
          "zone;\nuse `identify` to tell them apart.")
    return 0


def cmd_identify(config, fake_script):
    """Print every zone change so the team can map ids to floor positions."""

    def show(event):
        print(f"{time.strftime('%H:%M:%S')}  {event.key:>8}  "
              f"{'ON ' if event.occupied else 'off'}"
              f"  {names.get(event.key, '')}".rstrip())

    names = {key: name for name, key in config.zones.items()}
    stop = threading.Event()

    if fake_script:
        from .fake import FakeClient

        client = FakeClient(config, show, script_path=fake_script)
        client.run_forever(stop)
        return 0

    from .client import Fp2Client

    print("Walk into each zone. Ctrl+C to stop.")
    asyncio.run(Fp2Client(config, show, subscribe_all=True).run(stop, retry=False))
    return 0


def cmd_run(config, fake_script, telemetry_on):
    from .adapter import Fp2Input

    telemetry = None
    if telemetry_on:
        from telemetry import ZoneEventLog

        telemetry = ZoneEventLog(config.zones)

    source = Fp2Input(config, client_factory=make_client_factory(fake_script),
                      telemetry=telemetry).start()
    start = time.monotonic()
    print("Steering commands (Ctrl+C to stop):")
    try:
        while True:
            for command in source.poll():
                print(f"{(time.monotonic() - start) * 1000:9.0f} ms  "
                      f"{type(command).__name__}"
                      f"{' ' + command.direction.name if hasattr(command, 'direction') else ''}")
            time.sleep(POLL_S)
    finally:
        source.close()
    return 0


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        config = load(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.mode == "list" and args.fake:
        print("--fake has nothing to list; it needs the real sensor.",
              file=sys.stderr)
        return 2

    try:
        if args.mode == "list":
            return cmd_list(config)
        if args.mode == "identify":
            return cmd_identify(config, args.fake)
        return cmd_run(config, args.fake, args.telemetry)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print()
        return 0
    except Exception as exc:
        # A setup tool, not the game: say what went wrong in one line.
        print(f"FP2 error: {exc}", file=sys.stderr)
        logging.getLogger(__name__).debug("details", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
