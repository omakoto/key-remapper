#!/usr/bin/python3
#
# Remapper for https://www.amazon.com/gp/product/B00RM75NL0
#
import os
import sys
from typing import List

import evdev
from evdev import ecodes

import key_remapper

NAME = "Satechi Media Buttons remapper"
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON = os.path.join(SCRIPT_PATH, 'res/10key.png')

DEFAULT_DEVICE_NAME = "^Satechi Media Button Consumer Control"

MAP = {
    ecodes.KEY_VOLUMEUP: ecodes.KEY_VOLUMEUP,
    ecodes.KEY_VOLUMEDOWN: ecodes.KEY_VOLUMEDOWN,
    ecodes.KEY_PLAYPAUSE: ecodes.KEY_SPACE,
    ecodes.KEY_PREVIOUSSONG: ecodes.KEY_LEFT,
    ecodes.KEY_NEXTSONG: ecodes.KEY_RIGHT,
}

class Remapper(key_remapper.SimpleRemapper):
    def __init__(self):
        super().__init__(NAME, ICON, DEFAULT_DEVICE_NAME, match_non_keyboards=True)

    def handle_events(self, device: evdev.InputDevice, events: List[evdev.InputEvent]):
        for ev in events:
            if ev.type != ecodes.EV_KEY:
                continue

            key = MAP[ev.code]
            self.write_key_event(key, ev.value)


def main(args):
    remapper = Remapper()
    remapper.main(args)


if __name__ == '__main__':
    main(sys.argv[1:])
