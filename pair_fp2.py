"""Pair the laptop with the Aqara FP2 over HomeKit and SAVE the pairing.

Use this instead of `aiohomekitctl pair`: in aiohomekit 4.0.1 that command
pairs the device but saves an empty pairing file, so the keys are lost.

    python3 pair_fp2.py A65F <SETUP_CODE>
"""

import asyncio
import json
import pathlib
import re
import sys

from aiohomekit import Controller
from aiohomekit.zeroconf import ZeroconfServiceListener
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

PAIRING_FILE = pathlib.Path.home() / ".local/share/aiohomekit/pairing.json"
ALIAS = "fp2"


def fmt_pin(pin):
    digits = re.sub(r"\D", "", pin)
    if len(digits) != 8:
        sys.exit("The setup code must be 8 digits.")
    return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"


async def main(suffix, pin):
    zc = AsyncZeroconf()
    async with zc:
        browser = AsyncServiceBrowser(zc.zeroconf, ["_hap._tcp.local.", "_hap._udp.local."],
                                      listener=ZeroconfServiceListener())
        controller = Controller(async_zeroconf_instance=zc)
        async with controller:
            print("Scanning for 15 s...")
            await asyncio.sleep(15)
            target = None
            async for d in controller.async_discover(10):
                if d.description.name.upper().endswith(suffix.upper()):
                    target = d
            if target is None:
                sys.exit(f"No FP2 ending in {suffix} found on this network.")
            name, dev_id = target.description.name, target.description.id
            if target.paired:
                sys.exit(f"{name} ({dev_id}) is still paired to another controller. "
                         "Remove it from Apple Home / Home Assistant first.")

            print(f"Pairing with {name} ({dev_id})...")
            finish = await target.async_start_pairing(ALIAS)
            pairing = await finish(pin)

            # Save immediately, before anything else can fail.
            data = json.loads(PAIRING_FILE.read_text()) if PAIRING_FILE.exists() else {}
            data[ALIAS] = getattr(pairing, "pairing_data", None) or pairing._pairing_data
            PAIRING_FILE.parent.mkdir(parents=True, exist_ok=True)
            PAIRING_FILE.write_text(json.dumps(data, indent=2))
            PAIRING_FILE.chmod(0o600)
            print(f"Saved pairing '{ALIAS}' to {PAIRING_FILE}")

            accs = await pairing.list_accessories_and_characteristics()
            print(f"Verified: read {len(accs)} accessory record(s) from the FP2.")
        await browser.async_cancel()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], fmt_pin(sys.argv[2])))
