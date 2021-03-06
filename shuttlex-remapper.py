#!/usr/bin/python3
import math
import os
import sys
import threading
import time
from typing import List

import evdev
from evdev import ecodes, InputEvent

import key_remapper

NAME = "ShuttleXpress media controller 2"
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON = os.path.join(SCRIPT_PATH, 'res/knob.png')

DEFAULT_DEVICE_NAME = "Contour Design ShuttleXpress"

LEFT_RIGHT_KEYS = [ecodes.KEY_LEFT, ecodes.KEY_RIGHT, 'Left/Right']
VOLUME_KEYS = [ecodes.KEY_VOLUMEDOWN, ecodes.KEY_VOLUMEUP, 'VolUp/Down']
UP_DOWN_KEYS = [ecodes.KEY_UP, ecodes.KEY_DOWN, 'Up/Down']
KEY_MODES = [LEFT_RIGHT_KEYS, UP_DOWN_KEYS, VOLUME_KEYS]


def get_next_key_mode(mode: int) -> int:
    return (mode + 1) % len(KEY_MODES)


class Remapper(key_remapper.BaseRemapper):
    def __init__(self):
        super().__init__(NAME, ICON, DEFAULT_DEVICE_NAME)
        self.__lock = threading.RLock()
        self.__wheel_pos = 0
        self.__wheel_thread = threading.Thread(name='wheel-thread', target=self.__handle_wheel)
        self.__wheel_thread.setDaemon(True)
        self.__jog_mode = 0 # left / right keys
        self.__wheel_mode = 1 # vol up/down keys
        self.__button1_pressed = False
        self.__last_dial = 0

    # Thread safe
    def __set_wheel_pos(self, pos: int) -> None:
        with self.__lock:
            self.__wheel_pos = pos

    # Thread safe
    def __get_wheel_pos(self) -> int:
        with self.__lock:
            return self.__wheel_pos

    # Thread safe
    def __get_jog_mode(self):
        with self.__lock:
            return KEY_MODES[self.__jog_mode]

    # Thread safe
    def __get_wheel_mode(self):
        with self.__lock:
            return KEY_MODES[self.__wheel_mode]

    # Thread safe
    def __toggle_jog_mode(self):
        with self.__lock:
            self.__jog_mode = get_next_key_mode(self.__jog_mode)

    # Thread safe
    def __toggle_wheel_mode(self):
        with self.__lock:
            self.__wheel_mode = get_next_key_mode(self.__wheel_mode)

    def on_initialize(self):
        self.__wheel_thread.start()
        self.show_help()

    def show_help(self):
        key4 = 'KEY_F' if self.__button1_pressed else 'KEY_F11'
        key2 = 'Toggle Dial' if self.__button1_pressed else 'Toggle Jog'

        help = (f'[ALT] [{key2}] [KEY_SPACE] [{key4}] [KEY_MUTE]\n' +
                f'  Jog mode : {self.__get_jog_mode()[2]}\n' +
                f'  Dial mode: {self.__get_wheel_mode()[2]}')

        if not self.force_quiet:
            print(help)

        self.show_notification(help)

    def on_handle_events(self, device: evdev.InputDevice, events: List[evdev.InputEvent]):
        for ev in events:
            if ev.type == ecodes.EV_KEY:
                key = None
                value = 0

                # Remap the buttons.
                if ev.code == ecodes.BTN_4: # button 1 pressed
                    self.__button1_pressed = ev.value == 1
                    self.show_help()
                if ev.code == ecodes.BTN_5 and ev.value == 0: # toggle jog/dial mode
                    if self.__button1_pressed:
                        self.__toggle_wheel_mode()
                    else:
                        self.__toggle_jog_mode()
                    self.show_help()
                elif ev.code == ecodes.BTN_6 and ev.value == 0: # button 2 -> space
                    key = ecodes.KEY_SPACE
                elif ev.code == ecodes.BTN_7 and ev.value == 0: # button 4 -> F11
                    if self.__button1_pressed:
                        key = ecodes.KEY_F
                    else:
                        key = ecodes.KEY_F11
                elif ev.code == ecodes.BTN_8 and ev.value == 0: # button 5 -> mute
                    key = ecodes.KEY_MUTE

                if key:
                    self.press_key(key)
                continue

            # Handle the dial
            if ev.type == ecodes.EV_REL and ev.code == ecodes.REL_DIAL:
                now_dial = ev.value
                delta = now_dial - self.__last_dial
                self.__last_dial = now_dial

                key = 0
                if delta < 0:
                    key = self.__get_wheel_mode()[0]
                if delta > 0:
                    key = self.__get_wheel_mode()[1]

                if key != 0:
                    self.press_key(key)

            # Handle the jog
            if ev.type == ecodes.EV_REL and ev.code == ecodes.REL_WHEEL:
                self.__set_wheel_pos(ev.value)

    def __handle_wheel(self):
        jog_multiplier = 1.0

        sleep_duration = 0.1

        while True:
            time.sleep(sleep_duration)
            sleep_duration = 0.1

            current_wheel = self.__get_wheel_pos()

            # -7 <= current_wheel <= 7 is the range.
            if -1 <= current_wheel <= 1:
                continue

            # if debug: print(f'Wheel={current_wheel}')

            key = 0
            count = 0
            keys = self.__get_jog_mode()
            if current_wheel < 0:
                key = keys[0]
                count = -current_wheel
            elif current_wheel > 0:
                key = keys[1]
                count = current_wheel

            # Special case the small angles. Always make a single key event, and
            # don't repeat too fast.

            # range will be [1 - 7] * multiplier
            count = count - 1
            speed = math.pow(count, 2) + 1 # range 2 -
            sleep_duration = 0.8 / (jog_multiplier * speed)
            # print(f'{count}, {sleep_duration}')

            self.press_key(key)


def main(args):
    remapper = Remapper()
    remapper.main(args)


if __name__ == '__main__':
    main(sys.argv[1:])
