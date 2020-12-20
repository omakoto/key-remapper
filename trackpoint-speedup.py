#!/usr/bin/python3
#
# Remapper for https://www.amazon.com/gp/product/B00RM75NL0
#
import math
import os
import sys

import evdev
from evdev import ecodes, InputEvent

import key_remapper

NAME = "Trackpoint Spped-up"
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON = os.path.join(SCRIPT_PATH, 'res/trackpoint.png')

DEFAULT_DEVICE_NAME = "^TPPS/2 Elan TrackPoint"

# evtest output for the device:
# Input device ID: bus 0x11 vendor 0x2 product 0xa version 0x63
# Input device name: "TPPS/2 Elan TrackPoint"
# Supported events:
# Event type 0 (EV_SYN)
# Event type 1 (EV_KEY)
#   Event code 272 (BTN_LEFT)
#   Event code 273 (BTN_RIGHT)
#   Event code 274 (BTN_MIDDLE)
# Event type 2 (EV_REL)
#   Event code 0 (REL_X)
#   Event code 1 (REL_Y)


class Remapper(key_remapper.BaseRemapper):
    def __init__(self):
        super().__init__(NAME, ICON, DEFAULT_DEVICE_NAME,
                         match_non_keyboards=True, # Needed to read from non-keyboard devices.
                         # By default, you can only allows to send EV_KEY w/ KEY_* and BTN_* events.
                         # To send other events, you need to list all of them (including EV_KEY events) here.
                         uinput_events={
                             ecodes.EV_KEY: (ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE),
                             ecodes.EV_REL: (ecodes.REL_X, ecodes.REL_Y),
                         })
        self.threshold = 0
        self.add = 0
        self.power = 1

    def on_init_arguments(self, parser):
        parser.add_argument('--threshold', type=int, default=2, metavar='T')
        parser.add_argument('--add', type=float, default=2, metavar='V')
        parser.add_argument('--power', type=float, default=2.5, metavar='P')
        parser.add_argument('--scale', type=float, default=5, metavar='S')

    def on_arguments_parsed(self, args):
        self.threshold = args.threshold
        self.add = args.add
        self.power = args.power
        self.scale = args.scale

    def on_handle_event(self, device: evdev.InputDevice, ev: evdev.InputEvent):
        if ev.type == ecodes.EV_REL:
            value = math.fabs(ev.value) - self.threshold
            if value < 1:
                value = ev.value
            else:
                value = (value + self.add) / self.scale
                value = (math.pow(1 + value, self.power) - 1) * self.scale
                value = value + self.threshold

                if ev.value < 0:
                    value = -value

            if self.enable_debug:
                print(f'{ev.code}: {ev.value} -> {value}')

            ev.value = int(value)

        self.send_event(ev.type, ev.code, ev.value)


def main(args):
    remapper = Remapper()
    remapper.main(args)


if __name__ == '__main__':
    main(sys.argv[1:])
