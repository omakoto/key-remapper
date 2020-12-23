#!/usr/bin/python3
#
# Remapper for Topre Realfoce and the thinkpad internal keyboard.
#
import os
import sys
import threading
import time

import evdev
from evdev import ecodes as ec

import key_remapper

NAME = "Main Keyboard Remapper"
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON = os.path.join(SCRIPT_PATH, 'res/keyboard.png')

# AT Translated Set 2 keyboard -> thinkpad internal keyboard
# Topre Corporation Realforce  -> Realforce
# P. I. Engineering XK-16 HID  -> An external 8-key keyboard
DEFAULT_DEVICE_NAME = "^(AT Translated Set 2 keyboard|Topre Corporation Realforce|P. I. Engineering XK-16 HID)"

debug = False

# ESC + These keys will generate SHIFT+ALT+CTRL+META+[THE KEY]. I launch apps using them -- e.g. ESC+ENTER to launch
# Chrome.
VERSATILE_KEYS = (
    ec.KEY_F1,
    ec.KEY_F2,
    ec.KEY_F3,
    ec.KEY_F4,
    ec.KEY_F5,
    ec.KEY_F6,
    ec.KEY_F7,
    ec.KEY_F8,
    ec.KEY_F9,
    ec.KEY_F10,
    ec.KEY_F11,
    ec.KEY_F12,
    ec.KEY_ENTER,
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
        # Inject mouse wheel events periodically.
        # Example events:
        # Event: time 1608522295.791450, type 2 (EV_REL), code 8 (REL_WHEEL), value -1
        # Event: time 1608522295.791450, type 2 (EV_REL), code 11 (REL_WHEEL_HI_RES), value -120

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
                self.uinput.send_event(ec.EV_REL, ec.REL_WHEEL, vspeed)
                self.uinput.send_event(ec.EV_REL, ec.REL_WHEEL_HI_RES, vspeed * 120)
            if hspeed != 0:
                self.uinput.send_event(ec.EV_REL, ec.REL_HWHEEL, hspeed)
                self.uinput.send_event(ec.EV_REL, ec.REL_HWHEEL_HI_RES, hspeed * 120)

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

    def on_initialize(self):
        super().on_initialize()
        self.wheeler = Wheeler(self.new_mouse_uinput("_wheel"))
        self.wheeler.start()

    def on_device_lost(self):
        super().on_device_lost()
        self.wheeler.stop()

    def is_chrome(self):
        title, class_group_name, class_instance_name = self.get_active_window()
        return class_group_name == "Google-chrome"

    def on_handle_event(self, device: evdev.InputDevice, ev: evdev.InputEvent):
        if ev.type != ec.EV_KEY:
            return

        is_thinkpad = device.name.startswith('AT')
        is_xkeys = device.name.startswith('P. I.')

        # For x-keys. Convert to Shift+Ctrl+[number]
        if is_xkeys:
            # Special casing the first two keys.
            if self.matches_key(ev, ec.KEY_1, 1, ''): self.press_key(ec.KEY_BACK, done=True)
            if self.matches_key(ev, ec.KEY_2, 1, ''): self.press_key(ec.KEY_FORWARD, done=True)

            # Default setting...
            # These 8 keys send KEY_1 .. KEY_8, per my configuration.
            # Convert them into Shift+Ctrl+Alt+Meta+KEY
            if ev.value == 1:
                self.send_key_events(
                    (ec.KEY_LEFTSHIFT, 1),
                    (ec.KEY_LEFTCTRL, 1),
                    (ec.KEY_LEFTALT, 1),
                    (ec.KEY_LEFTMETA, 1),
                )
            self.send_ievent(ev)
            if ev.value == 0:
                self.send_key_events(
                    (ec.KEY_LEFTSHIFT, 0),
                    (ec.KEY_LEFTCTRL, 0),
                    (ec.KEY_LEFTALT, 0),
                    (ec.KEY_LEFTMETA, 0),
                )
            return

        # Thinkpad only: Use ins/del as pageup/down, unless CAPS is pressed.
        if is_thinkpad and not self.is_caps_pressed():
            if ev.code == ec.KEY_INSERT: ev.code = ec.KEY_PAGEUP
            elif ev.code == ec.KEY_DELETE: ev.code = ec.KEY_PAGEDOWN

        # Special ESC handling: Don't send "ESC-press" at key-down, but instead send it on key-*up*, unless
        # any keys are pressed between the down and up.
        # This allows to make "ESC + BACKSPACE" act as a DEL press without sending ESC.
        if ev.code == ec.KEY_ESC:
            if ev.value == 1:
                self.pending_esc_press = True
            if ev.value in (1, 2):
                return  # Ignore ESC down.

            # Here, ev.value must be 0.
            if self.pending_esc_press:
                self.pending_esc_press = False
                self.press_key(ec.KEY_ESC, reset_all_keys=False, done=True)
        else:
            # In order to allow combos like "ESC+ctrl+Backspace", don't clear pending ESC when modifier keys
            # are pressed.
            if ev.code not in (
                    ec.KEY_LEFTALT, ec.KEY_RIGHTALT,
                    ec.KEY_LEFTCTRL, ec.KEY_RIGHTCTRL,
                    ec.KEY_LEFTSHIFT, ec.KEY_RIGHTSHIFT,
                    ec.KEY_LEFTMETA, ec.KEY_RIGHTMETA,
                    ec.KEY_CAPSLOCK
            ):
                self.pending_esc_press = False

        # ESC (or shift) + backspace -> delete
        if self.matches_key(ev, ec.KEY_BACKSPACE, (1, 2), 'e'): self.press_key(ec.KEY_DELETE, done=True)
        if self.matches_key(ev, ec.KEY_BACKSPACE, (1, 2), 's'): self.press_key(ec.KEY_DELETE, done=True)

        # For chrome: -----------------------------------------------------------------------------------
        #  F5 -> back
        #  F6 -> forward
        if self.matches_key(ev, ec.KEY_F5, 1, '', self.is_chrome): self.press_key(ec.KEY_BACK, done=True)
        if self.matches_key(ev, ec.KEY_F6, 1, '', self.is_chrome): self.press_key(ec.KEY_FORWARD, done=True)

        # Global keys -----------------------------------------------------------------------------------

        # See VERSATILE_KEYS.
        if self.matches_key(ev, VERSATILE_KEYS, 1, 'e'): self.press_key(ev.code, 'acsw', done=True)

        # ESC + home/end -> ATL+Left/Right (back / forward)
        if self.matches_key(ev, ec.KEY_HOME, 1, 'e'): self.press_key(ec.KEY_LEFT, 'a', done=True)
        if self.matches_key(ev, ec.KEY_END, 1, 'e'): self.press_key(ec.KEY_RIGHT, 'a', done=True)

        # ESC + Pageup -> ctrl + pageup (prev tab)
        # ESC + Pagedown -> ctrl + pagedown (next tab)
        # (meaning ESC + ins/del act as them too on thinkpad.)
        if self.matches_key(ev, ec.KEY_PAGEUP, 1, 'e'): self.press_key(ec.KEY_PAGEUP, 'c', done=True)
        if self.matches_key(ev, ec.KEY_PAGEDOWN, 1, 'e'): self.press_key(ec.KEY_PAGEDOWN, 'c', done=True)

        # ESC + caps lock -> caps lock, in case I ever need it.
        if self.matches_key(ev, ec.KEY_CAPSLOCK, 1, 'e', ignore_other_modifiers=True): self.press_key(ec.KEY_CAPSLOCK, done=True)

        # # ESC + H / J / K / L -> LEFT, DOWN, UP, RIGHT
        # if self.matches_key(ev, ec.KEY_H, (1, 2), 'e', ignore_other_modifiers=True): self.press_key(ec.KEY_LEFT, "*", done=True)
        # if self.matches_key(ev, ec.KEY_J, (1, 2), 'e', ignore_other_modifiers=True): self.press_key(ec.KEY_DOWN, "*", done=True)
        # if self.matches_key(ev, ec.KEY_K, (1, 2), 'e', ignore_other_modifiers=True): self.press_key(ec.KEY_UP, "*", done=True)
        # if self.matches_key(ev, ec.KEY_L, (1, 2), 'e', ignore_other_modifiers=True): self.press_key(ec.KEY_RIGHT, "*", done=True)

        # ESC + H / J / K / L -> emulate wheel. Also support ESC+SPACE / C for left-hand-only scrolling.
        if self.matches_key(ev, (ec.KEY_J, ec.KEY_K, ec.KEY_SPACE, ec.KEY_C), (1, 0), 'e', ignore_other_modifiers=True):
            if ev.value == 0:
                self.wheeler.set_vwheel(0)
            elif ev.code in (ec.KEY_K, ec.KEY_C): # Scroll up
                self.wheeler.set_vwheel(1)
            elif ev.code in (ec.KEY_J, ec.KEY_SPACE): # Scroll down
                self.wheeler.set_vwheel(-1)
            return
        if self.matches_key(ev, (ec.KEY_L, ec.KEY_H), (1, 0), 'e', ignore_other_modifiers=True):
            if ev.value == 0:
                self.wheeler.set_hwheel(0)
            elif ev.code == ec.KEY_L: # Scroll right
                self.wheeler.set_hwheel(1)
            elif ev.code == ec.KEY_H: # Scroll left
                self.wheeler.set_hwheel(-1)
            return

        # Don't use capslock alone.
        if ev.code == ec.KEY_CAPSLOCK: return

        # Send the original event.
        self.send_ievent(ev)


def main(args):
    remapper = Remapper()
    remapper.main(args)


if __name__ == '__main__':
    main(sys.argv[1:])
