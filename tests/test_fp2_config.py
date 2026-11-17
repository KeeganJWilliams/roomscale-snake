"""Config validation: every failure has to say what to fix."""

import pathlib
import subprocess
import sys
import tempfile
import unittest

from input.fp2.config import ConfigError, load, parse

GOOD = {
    "alias": "fp2",
    "zones": {"center": "1.10", "up": "1.13", "down": "1.16",
              "left": "1.19", "right": "1.22"},
    "debounce_ms": 150,
    "lost_grace_ms": 1000,
}

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestParse(unittest.TestCase):
    def test_good_config(self):
        config = parse(GOOD)
        self.assertEqual(config.alias, "fp2")
        self.assertEqual(config.debounce_ms, 150)
        self.assertEqual(config.lost_grace_ms, 1000)
        self.assertEqual(sorted(config.subscriptions()),
                         [(1, 10), (1, 13), (1, 16), (1, 19), (1, 22)])

    def test_defaults_when_timings_are_omitted(self):
        raw = {"zones": GOOD["zones"]}
        config = parse(raw)
        self.assertEqual((config.alias, config.debounce_ms, config.lost_grace_ms),
                         ("fp2", 150, 1000))

    def test_missing_zone_names_them(self):
        raw = {"zones": {k: v for k, v in GOOD["zones"].items() if k != "down"}}
        with self.assertRaises(ConfigError) as caught:
            parse(raw)
        self.assertIn("down", str(caught.exception))

    def test_duplicate_zone_id_names_both_zones(self):
        raw = {"zones": dict(GOOD["zones"], left="1.13")}
        with self.assertRaises(ConfigError) as caught:
            parse(raw)
        message = str(caught.exception)
        self.assertIn("1.13", message)
        self.assertIn("left", message)
        self.assertIn("up", message)

    def test_unknown_zone_name_is_rejected(self):
        raw = {"zones": dict(GOOD["zones"], upp="1.25")}
        with self.assertRaises(ConfigError) as caught:
            parse(raw)
        self.assertIn("upp", str(caught.exception))

    def test_malformed_zone_id_is_rejected(self):
        for bad in ("13", "1.13.2", "one.13", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(ConfigError) as caught:
                    parse({"zones": dict(GOOD["zones"], up=bad)})
                self.assertIn("aid.iid", str(caught.exception))

    def test_missing_zones_object(self):
        with self.assertRaises(ConfigError):
            parse({"alias": "fp2"})

    def test_bad_timings_are_rejected(self):
        for field, value in (("debounce_ms", -1), ("debounce_ms", "soon"),
                             ("lost_grace_ms", None), ("debounce_ms", True)):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ConfigError) as caught:
                    parse(dict(GOOD, **{field: value}))
                self.assertIn(field, str(caught.exception))


class TestLoad(unittest.TestCase):
    def test_missing_file_says_so(self):
        with self.assertRaises(ConfigError) as caught:
            load("config/does_not_exist.json")
        self.assertIn("does_not_exist.json", str(caught.exception))

    def test_invalid_json_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "zones.json"
            path.write_text("{not json")
            with self.assertRaises(ConfigError) as caught:
                load(path)
            self.assertIn("valid JSON", str(caught.exception))

    def test_repo_config_is_valid(self):
        config = load(REPO_ROOT / "config/fp2_zones.json")
        self.assertEqual(len(config.zones), 5)

    def test_pairing_file_default_is_not_in_the_repo(self):
        config = parse(GOOD)
        self.assertNotIn(str(REPO_ROOT), str(config.pairing_file))
        self.assertEqual(config.char_cache_file.name, "charmap.json")

    def test_sample_fake_script_matches_the_repo_config(self):
        from input.fp2.fake import load_script

        config = load(REPO_ROOT / "config/fp2_zones.json")
        script, loop = load_script(REPO_ROOT / "config/fp2_fake_script.json",
                                   config.zones)
        self.assertTrue(loop)
        self.assertTrue(all(key in config.zones.values() for _, key, _ in script))


class TestOptionalDependency(unittest.TestCase):
    """aiohomekit must only be imported by input/fp2/client.py."""

    def test_game_imports_without_aiohomekit(self):
        code = (
            "import sys\n"
            "class Block:\n"
            "    def find_spec(self, name, path=None, target=None):\n"
            "        if name.split('.')[0] == 'aiohomekit':\n"
            "            raise AssertionError('aiohomekit was imported: ' + name)\n"
            "sys.meta_path.insert(0, Block())\n"
            "import main\n"
            "import input.fp2, input.fp2.adapter, input.fp2.steering, input.fp2.fake\n"
            "from input.fp2.config import load\n"
            "load('config/fp2_zones.json')\n"
            "assert 'aiohomekit' not in sys.modules\n"
            "print('clean')\n"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("clean", result.stdout)

    def test_gitignore_covers_pairing_data(self):
        ignored = (REPO_ROOT / ".gitignore").read_text()
        for pattern in ("pairing.json", "charmap.json", ".env", "telemetry/logs/"):
            self.assertIn(pattern, ignored)


if __name__ == "__main__":
    unittest.main()
