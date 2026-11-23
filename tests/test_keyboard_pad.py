"""The keyboard lights the d-pad panel the same way the FP2 does."""

import unittest

import pygame

from input.keyboard import FLASH_S, KeyboardInput


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def key(event_type, k):
    return pygame.event.Event(event_type, key=k)


class TestKeyboardPad(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.kb = KeyboardInput(clock=self.clock)

    def test_idle_shows_center(self):
        self.assertEqual(self.kb.zone_state().occupied, {"center"})

    def test_held_key_lights_its_square(self):
        self.kb.handle_event(key(pygame.KEYDOWN, pygame.K_LEFT))
        self.clock.now += 5
        self.assertEqual(self.kb.zone_state().occupied, {"left"})

    def test_tap_flashes_then_returns_to_center(self):
        self.kb.handle_event(key(pygame.KEYDOWN, pygame.K_w))
        self.kb.handle_event(key(pygame.KEYUP, pygame.K_w))
        self.assertEqual(self.kb.zone_state().occupied, {"up"})
        self.clock.now += FLASH_S + 0.01
        self.assertEqual(self.kb.zone_state().occupied, {"center"})

    def test_still_steers(self):
        self.kb.handle_event(key(pygame.KEYDOWN, pygame.K_RIGHT))
        (turn,) = self.kb.poll()
        self.assertEqual(turn.direction.name, "RIGHT")
        self.assertFalse(self.kb.zone_state().lost)


if __name__ == "__main__":
    unittest.main()
