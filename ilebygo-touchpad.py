#!/usr/bin/python3
#
# Remapper for https://www.amazon.com/gp/product/B0776T8QDC
#
# Use 3 finger swipe for back/forward (rather than app-switch)
#
import os
import sys
from typing import List

import evdev
import key_remapper
from evdev import ecodes, InputEvent

NAME = "Main Keyboard Remapper"
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON = os.path.join(SCRIPT_PATH, 'res/trackpad.png')

DEFAULT_DEVICE_NAME = "^USB USB Device Keyboard"
ID_REGEX = "^v0c45 p8101"

class Remapper(key_remapper.BaseRemapper):
    def __init__(self):
        super().__init__(NAME, ICON, DEFAULT_DEVICE_NAME, id_regex=ID_REGEX)
        self.lshift = True
        self.lalt = True

    def on_device_detected(self, devices: List[evdev.InputDevice]):
        super().on_device_detected(devices)

    def on_handle_event(self, device: evdev.InputDevice, ev: evdev.InputEvent):
        if ev.type != ecodes.EV_KEY:
            return

        if ev.code == ecodes.KEY_TAB and ev.value == 1:
            if self.lalt:
                if self.lshift:
                    self.press_key(ecodes.KEY_BACK)
                else:
                    self.press_key(ecodes.KEY_FORWARD)
            self.lshift = False
            self.lalt = False
            return

        if ev.code == ecodes.KEY_LEFTSHIFT and ev.value == 1:
            self.lshift = True
            return
        if ev.code == ecodes.KEY_LEFTALT and ev.value == 1:
            self.lalt = True
            return


def main(args):
    remapper = Remapper()
    remapper.main(args)


if __name__ == '__main__':
    main(sys.argv[1:])

# 3 finger left
# Event: time 1608411869.141771, type 4 (EV_MSC), code 4 (MSC_SCAN), value 700e1
# Event: time 1608411869.141771, type 1 (EV_KEY), code 42 (KEY_LEFTSHIFT), value 1
# Event: time 1608411869.141771, type 4 (EV_MSC), code 4 (MSC_SCAN), value 700e2
# Event: time 1608411869.141771, type 1 (EV_KEY), code 56 (KEY_LEFTALT), value 1
# Event: time 1608411869.141771, type 4 (EV_MSC), code 4 (MSC_SCAN), value 7002b
# Event: time 1608411869.141771, type 1 (EV_KEY), code 15 (KEY_TAB), value 1
# Event: time 1608411869.141771, -------------- SYN_REPORT ------------
# Event: time 1608411869.148288, type 4 (EV_MSC), code 4 (MSC_SCAN), value 7002b
# Event: time 1608411869.148288, type 1 (EV_KEY), code 15 (KEY_TAB), value 0
# Event: time 1608411869.148288, -------------- SYN_REPORT ------------
# Event: time 1608411869.172285, type 4 (EV_MSC), code 4 (MSC_SCAN), value 7002b
# Event: time 1608411869.172285, type 1 (EV_KEY), code 15 (KEY_TAB), value 1
# Event: time 1608411869.172285, -------------- SYN_REPORT ------------
# Event: time 1608411869.178285, type 4 (EV_MSC), code 4 (MSC_SCAN), value 7002b
# Event: time 1608411869.178285, type 1 (EV_KEY), code 15 (KEY_TAB), value 0
#  :
# Event: time 1608411869.255305, -------------- SYN_REPORT ------------
# Event: time 1608411869.302308, type 4 (EV_MSC), code 4 (MSC_SCAN), value 700e1
# Event: time 1608411869.302308, type 1 (EV_KEY), code 42 (KEY_LEFTSHIFT), value 0
# Event: time 1608411869.302308, type 4 (EV_MSC), code 4 (MSC_SCAN), value 700e2
# Event: time 1608411869.302308, type 1 (EV_KEY), code 56 (KEY_LEFTALT), value 0
# Event: time 1608411869.302308, -------------- SYN_REPORT ------------
#
# # 3 finger right
# Event: time 1608411893.871130, type 4 (EV_MSC), code 4 (MSC_SCAN), value 700e2
# Event: time 1608411893.871130, type 1 (EV_KEY), code 56 (KEY_LEFTALT), value 1
# Event: time 1608411893.871130, type 4 (EV_MSC), code 4 (MSC_SCAN), value 7002b
# Event: time 1608411893.871130, type 1 (EV_KEY), code 15 (KEY_TAB), value 1
# Event: time 1608411893.871130, -------------- SYN_REPORT ------------
# Event: time 1608411893.876758, type 4 (EV_MSC), code 4 (MSC_SCAN), value 7002b
# Event: time 1608411893.876758, type 1 (EV_KEY), code 15 (KEY_TAB), value 0
# Event: time 1608411893.876758, -------------- SYN_REPORT ------------
# Event: time 1608411893.903748, type 4 (EV_MSC), code 4 (MSC_SCAN), value 7002b
# Event: time 1608411893.903748, type 1 (EV_KEY), code 15 (KEY_TAB), value 1
# Event: time 1608411893.903748, -------------- SYN_REPORT ------------
# Event: time 1608411893.909773, type 4 (EV_MSC), code 4 (MSC_SCAN), value 7002b
# Event: time 1608411893.909773, type 1 (EV_KEY), code 15 (KEY_TAB), value 0
# :
# Event: time 1608411903.930785, -------------- SYN_REPORT ------------
# Event: time 1608411904.429705, type 4 (EV_MSC), code 4 (MSC_SCAN), value 700e1
# Event: time 1608411904.429705, type 1 (EV_KEY), code 42 (KEY_LEFTSHIFT), value 0
# Event: time 1608411904.429705, type 4 (EV_MSC), code 4 (MSC_SCAN), value 700e2
# Event: time 1608411904.429705, type 1 (EV_KEY), code 56 (KEY_LEFTALT), value 0
# Event: time 1608411904.429705, -------------- SYN_REPORT ------------
