#!/usr/bin/python3
#
# Remapper for Topre Realfoce and the thinkpad internal keyboard.
#
import os
import sys
import threading
import time

import evdev
from evdev import ecodes

import key_remapper

NAME = "Main Keyboard Remapper"
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON = os.path.join(SCRIPT_PATH, 'res/keyboard.png')

# AT Translated Set 2 keyboard -> thinkpad internal keyboard
# Topre Corporation Realforce  -> Realforce
# P. I. Engineering XK-16 HID  -> An external 8-key keyboards.
DEFAULT_DEVICE_NAME = "^(AT Translated Set 2 keyboard|Topre Corporation Realforce|P. I. Engineering XK-16 HID)"

debug = False

VERSATILE_KEYS = (
    ecodes.KEY_F1,
    ecodes.KEY_F2,
    ecodes.KEY_F3,
    ecodes.KEY_F4,
    ecodes.KEY_F5,
    ecodes.KEY_F6,
    ecodes.KEY_F7,
    ecodes.KEY_F8,
    ecodes.KEY_F9,
    ecodes.KEY_F10,
    ecodes.KEY_F11,
    ecodes.KEY_F12,
    ecodes.KEY_ENTER,
)

class Wheeler:
    """Send mouse wheel events periodically
    """
    def __init__(self, uinput: key_remapper.SyncedUinput):
        self.__lock = threading.Lock()

        self.uinput:key_remapper.SyncedUinput = uinput

        self.__wheel_thread = threading.Thread(name='wheel-thread', target=self.__do_wheel)
        self.__wheel_thread.setDaemon(True)

        self.__event = threading.Event()

        self.__vwheel_speed = 0  # Vertical wheel speed and direction: ..., -1, 0, 1, ....
        self.__hwheel_speed = 0  # Vertical wheel speed and direction: ..., -1, 0, 1, ....

        self.wheel_repeat_delay_normal_ms = 0.020
        self.wheel_repeat_delay_fast_ms = 0.005
        self.wheel_make_fast_after_this_many_events = 10

    def __do_wheel(self):
        # Inject
        #Event: time 1608522295.791450, type 2 (EV_REL), code 8 (REL_WHEEL), value -1
        #Event: time 1608522295.791450, type 2 (EV_REL), code 11 (REL_WHEEL_HI_RES), value -120

        consecutive_event_count = 0
        while True:
            vspeed = 0
            hspeed = 0
            with self.__lock:
                vspeed = self.__vwheel_speed
                hspeed = self.__hwheel_speed

            if False:
                print(f'# wheel: {vspeed} - {hspeed}')

            if vspeed != 0:
                self.uinput.send_event(ecodes.EV_REL, ecodes.REL_WHEEL, vspeed)
                self.uinput.send_event(ecodes.EV_REL, ecodes.REL_WHEEL_HI_RES, vspeed * 120)
            if hspeed != 0:
                self.uinput.send_event(ecodes.EV_REL, ecodes.REL_HWHEEL, hspeed)
                self.uinput.send_event(ecodes.EV_REL, ecodes.REL_HWHEEL_HI_RES, hspeed * 120)

            if vspeed == 0 and hspeed == 0:
                consecutive_event_count = 0
                self.__event.wait()
                self.__event.clear()
            else:
                consecutive_event_count += 1

            delay = self.wheel_repeat_delay_normal_ms
            if consecutive_event_count > self.wheel_make_fast_after_this_many_events:
                delay = self.wheel_repeat_delay_fast_ms
            time.sleep(delay)

    def start(self):
        self.__wheel_thread.start()

    def set_vwheel(self, speed: int):
        if debug: print(f'# vwheel: {speed}')
        with self.__lock:
            self.__vwheel_speed = speed
        self.__event.set()

    def set_hwheel(self, speed: int):
        if debug: print(f'# hwheel: {speed}')
        with self.__lock:
            self.__hwheel_speed = speed
        self.__event.set()

    def stop(self):
        self.set_vwheel(0)
        self.set_hwheel(0)

class Remapper(key_remapper.BaseRemapper):
    def __init__(self):
        super().__init__(NAME, ICON, DEFAULT_DEVICE_NAME)
        self.pending_esc_press = False

        self.wheeler = Wheeler(self.new_mouse_uinput("_wheel"))

    def on_initialize(self):
        super().on_initialize()
        self.wheeler.start()

    def on_device_lost(self):
        super().on_device_lost()
        self.wheeler.stop()

    def is_chrome(self):
        active_window = self.get_active_window()
        cls = active_window[1]
        return cls == "Google-chrome"

    def on_handle_event(self, device: evdev.InputDevice, ev: evdev.InputEvent):
        if ev.type != ecodes.EV_KEY:
            return

        is_thinkpad = device.name.startswith('AT')
        is_xkeys = device.name.startswith('P. I.')

        # For x-keys. Convert to Shift+Ctrl+[number]
        if is_xkeys:
            # These 8 keys send KEY_1 .. KEY_8, per my configuration.
            # Convert them into Shift+Ctrl+KEY
            if ev.value == 1:
                self.send_key_events(
                    (ecodes.KEY_LEFTSHIFT, 1),
                    (ecodes.KEY_LEFTCTRL, 1))
            self.send_ievent(ev)
            if ev.value == 0:
                self.send_key_events(
                    (ecodes.KEY_LEFTSHIFT, 0),
                    (ecodes.KEY_LEFTCTRL, 0))
            return

        # Thinkpad only: Use ins/del as pageup/down, unless CAPS is pressed.
        if is_thinkpad:
            if ev.code == ecodes.KEY_INSERT and not self.is_caps_pressed(): ev.code = ecodes.KEY_PAGEUP
            elif ev.code == ecodes.KEY_DELETE and not self.is_caps_pressed(): ev.code = ecodes.KEY_PAGEDOWN

        # Special ESC handling: Don't send "ESC-press" at key-down, but instead send it on key-*up*, unless
        # any keys are pressed between the down and up.
        # This allows to make "ESC + BACKSPACE" act as a DEL press without sending ESC.
        if ev.code == ecodes.KEY_ESC:
            if ev.value == 1:
                self.pending_esc_press = True
            if ev.value in (1, 2):
                return  # Ignore ESC down.

            # Here, ev.value must be 0.
            if self.pending_esc_press:
                self.pending_esc_press = False
                self.press_key(ecodes.KEY_ESC, reset_all_keys=False, done=True)
        else:
            # In order to allow combos like "ALT+ESC", don't clear pending ESC when modifier keys are pressed.
            if ev.code not in (
                    ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT,
                    ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL,
                    ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
                    ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA,
                    ecodes.KEY_CAPSLOCK
            ):
                self.pending_esc_press = False

        # ESC (or shift) + backspace -> delete
        if self.matches_key(ev, ecodes.KEY_BACKSPACE, (1, 2), 'e'): self.press_key(ecodes.KEY_DELETE, done=True)
        if self.matches_key(ev, ecodes.KEY_BACKSPACE, (1, 2), 's'): self.press_key(ecodes.KEY_DELETE, done=True)

        # For chrome: -----------------------------------------------------------------------------------
        #  F5 -> back
        #  F6 -> forward
        if self.matches_key(ev, ecodes.KEY_F5, 1, '', self.is_chrome): self.press_key(ecodes.KEY_BACK, done=True)
        if self.matches_key(ev, ecodes.KEY_F6, 1, '', self.is_chrome): self.press_key(ecodes.KEY_FORWARD, done=True)

        # Global keys -----------------------------------------------------------------------------------

        # Convert ESC + Function key to ALT+SHIFT+CTRL+META + Function key, for versatile shortcuts.
        if self.matches_key(ev, VERSATILE_KEYS, 1, 'e'): self.press_key(ev.code, 'acsw', done=True)

        # ESC + home/end -> ATL+Left/Right (back / forward)
        if self.matches_key(ev, ecodes.KEY_HOME, 1, 'e'): self.press_key(ecodes.KEY_LEFT, 'a', done=True)
        if self.matches_key(ev, ecodes.KEY_END, 1, 'e'): self.press_key(ecodes.KEY_RIGHT, 'a', done=True)

        # ESC + space -> page up. (for chrome and also in-process browser, such as Markdown Preview in vs code)
        if self.matches_key(ev, ecodes.KEY_SPACE, (1, 2), 'e'): self.press_key(ecodes.KEY_PAGEUP, done=True)

        # ESC + Pageup -> ctrl + pageup (prev tab)
        # ESC + Pagedown -> ctrl + pagedown (next tab)
        # (meaning ESC + ins/del act as them too on thinkpad.)
        if self.matches_key(ev, ecodes.KEY_PAGEUP, 1, 'e'): self.press_key(ecodes.KEY_PAGEUP, 'c', done=True)
        if self.matches_key(ev, ecodes.KEY_PAGEDOWN, 1, 'e'): self.press_key(ecodes.KEY_PAGEDOWN, 'c', done=True)

        # ESC + caps lock -> caps lock, in case I ever need it.
        if self.matches_key(ev, ecodes.KEY_CAPSLOCK, 1, 'e', ignore_other_modifiers=True): self.press_key(ecodes.KEY_CAPSLOCK, done=True)

        # # ESC + H / J / K / L -> LEFT, DOWN, UP, RIGHT
        # if self.matches_key(ev, ecodes.KEY_H, (1, 2), 'e', ignore_other_modifiers=True): self.press_key(ecodes.KEY_LEFT, "*", done=True)
        # if self.matches_key(ev, ecodes.KEY_J, (1, 2), 'e', ignore_other_modifiers=True): self.press_key(ecodes.KEY_DOWN, "*", done=True)
        # if self.matches_key(ev, ecodes.KEY_K, (1, 2), 'e', ignore_other_modifiers=True): self.press_key(ecodes.KEY_UP, "*", done=True)
        # if self.matches_key(ev, ecodes.KEY_L, (1, 2), 'e', ignore_other_modifiers=True): self.press_key(ecodes.KEY_RIGHT, "*", done=True)

        # ESC + H / J / K / L -> emulate wheel.
        if self.matches_key(ev, (ecodes.KEY_J, ecodes.KEY_K), (1, 0), 'e', ignore_other_modifiers=True):
            if ev.value == 0:
                self.wheeler.set_vwheel(0)
            elif ev.code == ecodes.KEY_K:
                self.wheeler.set_vwheel(1)
            elif ev.code == ecodes.KEY_J:
                self.wheeler.set_vwheel(-1)
            return
        if self.matches_key(ev, (ecodes.KEY_L, ecodes.KEY_H), (1, 0), 'e', ignore_other_modifiers=True):
            if ev.value == 0:
                self.wheeler.set_hwheel(0)
            elif ev.code == ecodes.KEY_L:
                self.wheeler.set_hwheel(1)
            elif ev.code == ecodes.KEY_H:
                self.wheeler.set_hwheel(-1)
            return

        # Don't use capslock alone.
        if ev.code == ecodes.KEY_CAPSLOCK: return

        # Send the original event.
        self.send_ievent(ev)


def main(args):
    remapper = Remapper()
    remapper.main(args)


if __name__ == '__main__':
    main(sys.argv[1:])