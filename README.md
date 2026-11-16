# roomscale-snake

Snake projected onto the floor of the Georgia Tech Aware Home. The player
steers by stepping onto a taped 3x3 d-pad; an **Aqara FP2** mmWave presence
sensor reports which zone they are standing in.

## Running

```
pip install -r requirements.txt

python main.py --input keyboard                              # no sensor needed
python main.py --input fp2                                   # paired FP2
python main.py --input fp2 --fake config/fp2_fake_script.json  # replay, no hardware
python main.py --input both                                  # keyboard + FP2
```

Keyboard: arrow keys / WASD steer, SPACE starts or restarts, P pauses,
F11 fullscreen, ESC quits. `--input both` keeps the keyboard live next to
the sensor, which is what facilitators want during testing.

Layout: `engine/` (grid, tick loop, snake, collisions, game states),
`input/` (keyboard + FP2), `render/` (pygame drawing, homography later),
`objects/` (ArUco), `ambient/` (Home Assistant events), `telemetry/`
(latency logs for objective O3).

Every input source produces the same `Command`s - `Turn`, `PlayerLost`,
`PlayerFound` (see `input/base.py`) - so the Engine never learns which
device steered it.

## FP2 setup

The FP2 has no local API of its own, so the game laptop talks to it over
HomeKit (HAP over IP on the LAN) with `aiohomekit`. No Home Assistant in
this path.

**A HomeKit accessory can only be paired to one controller at a time.**
The game laptop owns the pairing, so the FP2 must not also be added to
Apple Home or Home Assistant. Remove it there first.

### 1. Draw the zones (once, phone)

In the Aqara Home app, draw five zones on the floor plan matching the tape:

```
 [dead] [ up  ] [dead]
 [left] [center] [right]
 [dead] [down ] [dead]
```

Corners stay unassigned. Each zone becomes its own HomeKit Occupancy
Sensor; there is also one sensor covering the whole detection area.

### 2. Pair (once, on the game laptop, with the sensor in hand)

Needs the physical sensor and its 8-digit setup code:

```
pip install aiohomekit
python3 pair_fp2.py A65F <SETUP_CODE>    # A65F = end of the sensor's name, e.g. Presence-Sensor-FP2-A65F
```

Use `pair_fp2.py`, not `aiohomekitctl pair`: in aiohomekit 4.0.1 the CLI
pairs the sensor but saves an empty pairing file, which leaves the FP2
locked to keys nobody has. The FP2 must first be removed from Apple Home /
Home Assistant (a HomeKit device has one controller), and its Device ID
changes every time its pairing is reset, which is why the script finds it
by name. Re-adding the FP2 in the Aqara app resets the pairing; just rerun
`pair_fp2.py`.

That writes `~/.local/share/aiohomekit/pairing.json`. **Never commit that
file or a setup code** - `pairing.json`, `charmap.json` and `.env` are in
`.gitignore`.

### 3. Map zones to directions

HomeKit zone names don't reliably match the Aqara app's names or
numbering, so zones are identified by `aid.iid`:

```
python -m input.fp2 list       # every occupancy sensor, as aid.iid + name
python -m input.fp2 identify   # walk each zone and watch which id turns on
```

`identify` prints `HH:MM:SS  1.13  ON/off`. Walk into each taped zone in
turn and write the ids into `config/fp2_zones.json`:

```json
{
  "alias": "fp2",
  "zones": {"center": "1.10", "up": "1.13", "down": "1.16", "left": "1.19", "right": "1.22"},
  "debounce_ms": 150,
  "lost_grace_ms": 1000
}
```

All five names are required and the ids must be distinct; the loader says
exactly what to fix otherwise. Check the mapping with:

```
python -m input.fp2 run        # prints TURN / PlayerLost / PlayerFound
```

### Tuning

- `debounce_ms` (150): how long one zone must hold before it counts as a
  turn. Raising it rejects more accidental brushes but adds latency.
- `lost_grace_ms` (1000): how long the pad may read empty before the game
  pauses. The FP2 can briefly report every zone off mid-step, so this
  cannot be much lower.
- Zone sensitivity and size are tuned in the Aqara app, not in code.

### When the sensor isn't there

The FP2 client runs on a daemon background thread. If it can't connect, or
the connection drops, the game logs it, pauses (`PlayerLost`) and keeps
retrying with backoff up to 30s. It never crashes the game, and a sensor
that comes back needs no restart. A bad *config*, by contrast, fails
immediately with a message - that's a setup mistake worth catching early.

`aiohomekit` is imported only by `input/fp2/client.py`, so the rest of the
game runs on a machine that never installed it.

## Telemetry (objective O3)

With `--input fp2`, every zone event is logged to
`telemetry/logs/fp2_zones_<timestamp>.csv`:

```
t_recv_ns, zone_key, zone_name, occupied, command_emitted, t_command_ns
```

A row's command columns are filled in when that event caused a command, so
`t_command_ns - t_recv_ns` is the sensor-to-command latency. Pass
`--no-telemetry` to skip the file.

Note that this latency **includes `debounce_ms` by construction** - a turn
cannot be emitted sooner than 150 ms after the zone first reads occupied.
The proposal's target (median <= 150 ms, 95th <= 250 ms sensor to
projection) therefore needs either a smaller `debounce_ms` or the budget
measured from "zone held" rather than "zone first seen". `Turn` carries
`t_recv_ns` so Render can add the frame timestamp and close out the
measurement.

All timestamps on the input path come from `time.monotonic_ns()`
(`input.base.now_ns`). Engine events use `time.perf_counter_ns()`, a
different epoch - only subtract stamps from the same clock.

## Tests

```
python -m pytest
```

No FP2 is needed: the steering state machine is pure with an injectable
clock, the adapter is tested against a scripted fake client, and
`--fake` replays an event file end to end.
