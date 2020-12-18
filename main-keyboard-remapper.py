#!/usr/bin/python3
import os
import sys

import evdev
import key_remapper
from evdev import ecodes, InputEvent

NAME = "Main Keyboard Remapper"
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
ICON = os.path.join(SCRIPT_PATH, 'res/keyboard.png')

DEFAULT_DEVICE_NAME = "^(AT Translated Set 2 keyboard|Topre Corporation Realforce|P. I. Engineering XK-16 HID)"

debug = False

class Remapper(key_remapper.SimpleRemapper):
    def __init__(self):
        super().__init__(NAME, ICON, DEFAULT_DEVICE_NAME)

    def is_chrome(self):
        active_window = self.get_active_window()
        cls = active_window[1]
        return cls == "Google-chrome"

    def handle_event(self, device: evdev.InputDevice, ev: evdev.InputEvent):
        if ev.type != ecodes.EV_KEY:
            return

        is_thinkpad = device.name.startswith('AT')
        is_xkeys = device.name.startswith('P. I.')

        # For x-keys. Convert to Shift+Ctrl+[number]
        if is_xkeys:
            if ecodes.KEY_1 <= ev.code <= ecodes.KEY_8 and ev.value == 1:
                self.press_key(ecodes.KEY_DELETE, 'cs')
            return

        # Thinkpad only: Use ins/del as pageup/down, unless CAPS is pressed.
        if is_thinkpad:
            if ev.code == ecodes.KEY_INSERT and not self.is_caps_pressed(): ev.code = ecodes.KEY_PAGEUP
            elif ev.code == ecodes.KEY_DELETE and not self.is_caps_pressed(): ev.code = ecodes.KEY_PAGEDOWN

        # Also shift or esc + backspace -> delete
        if self.matches_key(ev, ecodes.KEY_BACKSPACE, 1, 's'): self.press_key(ecodes.KEY_DELETE, done=True)
        if self.matches_key(ev, ecodes.KEY_BACKSPACE, 1, 'e'): self.press_key(ecodes.KEY_DELETE, done=True)

        # For chrome: -----------------------------------------------------------------------------------
        #  F5 -> back
        #  F6 -> forward
        if self.matches_key(ev, ecodes.KEY_F5, 1, '', self.is_chrome): self.press_key(ecodes.KEY_BACK, done=True)
        if self.matches_key(ev, ecodes.KEY_F6, 1, '', self.is_chrome): self.press_key(ecodes.KEY_FORWARD, done=True)

        # Global ----------------------------------------------------------------------------------------

        # ESC + F11 -> CTRL+ATL+1 -> work.txt
        if self.matches_key(ev, ecodes.KEY_F11, 1, 'e'): self.press_key(ecodes.KEY_MINUS, 'ac', done=True)

        # ESC + F12 -> CTRL+ATL+T -> terminal
        if self.matches_key(ev, ecodes.KEY_F12, 1, 'e'): self.press_key(ecodes.KEY_T, 'ac', done=True)

        # ESC + ENTER -> CTRL+ATL+1 -> chrome
        if self.matches_key(ev, ecodes.KEY_ENTER, 1, 'e'): self.press_key(ecodes.KEY_C, 'ac', done=True)

        # ESC + home/end -> ATL+Left/Right (back / forwward)
        if self.matches_key(ev, ecodes.KEY_HOME, 1, 'e'): self.press_key(ecodes.KEY_LEFT, 'a', done=True)
        if self.matches_key(ev, ecodes.KEY_END, 1, 'e'): self.press_key(ecodes.KEY_RIGHT, 'a', done=True)

        # ESC + space -> page up. (for chrome and also in-process browser, such as Markdown Preview in vs code)
        if self.matches_key(ev, ecodes.KEY_SPACE, (1, 2), 'e'): self.press_key(ecodes.KEY_PAGEUP, done=True)

        #  ESC + Pageup -> ctrl + pageup (prev tab)
        #  ESC + Pagedown -> ctrl + pagedown (next tab)
        if self.matches_key(ev, ecodes.KEY_PAGEUP, 1, 'e'): self.press_key(ecodes.KEY_PAGEUP, 'c', done=True)
        if self.matches_key(ev, ecodes.KEY_PAGEDOWN, 1, 'e'): self.press_key(ecodes.KEY_PAGEDOWN, 'c', done=True)

        # esc + caps -> caps
        if self.matches_key(ev, ecodes.KEY_CAPSLOCK, 1, 'ep'): self.press_key(ecodes.KEY_CAPSLOCK, done=True)

        # Don't use capslock
        if ev.code == ecodes.KEY_CAPSLOCK: return # don't use capslock

        self.uinput.write([InputEvent(0, 0, ecodes.EV_KEY, ev.code, ev.value)])


def main(args):
    remapper = Remapper()
    remapper.main(args)


if __name__ == '__main__':
    main(sys.argv[1:])
