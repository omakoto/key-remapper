#!/usr/bin/python3
import argparse
import collections
import fcntl
import os
import random
import re
import sys
import threading
import traceback
from typing import Optional, Dict, List, TextIO, Tuple, Union, Iterable, Callable

import evdev
import gi
import notify2
import pyudev
from evdev import UInput, ecodes as e, ecodes

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Wnck', '3.0')
from gi.repository import Gtk as gtk
from gi.repository import Wnck as wnck
from gi.repository import GLib as glib
from gi.repository import AppIndicator3 as appindicator

debug = False
quiet = False

# Uinput device name used by this instance.
UINPUT_DEVICE_NAME = 'key-remapper-uinput'


MAIN_FILE_NANE = re.sub('''\..*?$''', "", os.path.basename(sys.argv[0]))

# My own at-exit handling.
_at_exists = []


def add_at_exit(callback):
    _at_exists.append(callback)


def call_at_exists():
    for callback in _at_exists:
        callback()
    _at_exists.clear()


def exit(status_code):
    """Exit() with add_at_exit support.
    """
    call_at_exists()
    sys.exit(status_code)


__singleton_lock_file = None  # Store the file in it to prevent auto-closing.


def ensure_singleton(global_lock_name):
    file = f'/tmp/{global_lock_name}.lock'
    if debug:
        print(f'Lockfile: {file}')
    try:
        os.umask(0o000)
        global __singleton_lock_file
        __singleton_lock_file = open(file, 'w')
        fcntl.flock(__singleton_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        raise SystemExit(f'Unable to obtain file lock {file}. Previous process running.')


def is_syn(ev: evdev.InputEvent) -> bool:
    """Returns if an event is a SYN event.
    """
    return ev and ev.type == ecodes.EV_SYN and ev.code == ecodes.SYN_REPORT and ev.value == 0


class SyncedUinput:
    """Thread safe wrapper for uinput.
    """
    wrapped: evdev.uinput
    __lock: threading.RLock
    __key_states: Dict[int, int]

    def __init__(self, uinput: evdev.UInput):
        self.wrapped = uinput
        self.__lock = threading.RLock()
        self.__key_states = collections.defaultdict(int)

    def write(self, *events: evdev.InputEvent):
        with self.__lock:
            last_event = None
            for ev in events:
                if is_syn(ev) and is_syn(last_event):
                    # Don't send syn twice in a row.
                    # (Not sure if it matters but just in case.)
                    continue

                # When sending a KEY event, only send what'd make sense given the
                # current key state.
                if ev.type == ecodes.EV_KEY:
                    old_state = self.__key_states[ev.code]
                    if ev.value == 0:
                        if old_state == 0:  # Don't send if already released.
                            continue
                    elif ev.value == 1:
                        if old_state > 0:  # Don't send if already pressed.
                            continue
                    elif ev.value == 2:
                        if old_state == 0:  # Don't send if not pressed.
                            continue

                    self.__key_states[ev.code] = ev.value

                self.wrapped.write_event(ev)
                last_event = ev

            # If any event was written, and the last event isn't a syn, send one.
            if last_event and not is_syn(last_event):
                self.wrapped.syn()

    def get_key_state(self, key: int):
        with self.__lock:
            return self.__key_states[key]

    def reset(self):
        # Release all pressed keys.
        with self.__lock:
            try:
                for key, value in self.__key_states.items():
                    if value > 0:
                        self.wrapped.write(ecodes.EV_KEY, key, 0)
                        self.wrapped.syn()
            except:
                pass  # ignore any exception
            finally:
                self.__key_states.clear()

    def close(self):
        with self.__lock:
            self.reset()
            if self.wrapped:
                self.wrapped.close()
                self.wrapped = None

    def __str__(self) -> str:
        return f'SyncedUinput[{self.wrapped}]'

    def send_event(self, type: int, key: int, value: int) -> None:
        with self.__lock:
            self.write(evdev.InputEvent(0, 0, type, key, value))

class TaskTrayIcon:
    def __init__(self, name, icon_path):
        self.name = name
        self.icon_path = icon_path
        self.indicator = appindicator.Indicator.new(name, icon_path,
                                                    appindicator.IndicatorCategory.SYSTEM_SERVICES)
        self.indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.__build_menu())

    def _add_menu_items(self, menu):
        item_quit = gtk.MenuItem(f'Exit {self.name}')
        item_quit.connect('activate', self.quit)
        menu.append(item_quit)

    def __build_menu(self):
        menu = gtk.Menu()

        self._add_menu_items(menu)

        menu.show_all()
        return menu

    def _on_quit(self):
        pass

    def quit(self, source):
        quit(self._on_quit)

    def set_icon(self, icon_path):
        self.icon_path = icon_path

        def inner():
            self.indicator.set_icon_full(self.icon_path, '')

        glib.idle_add(inner)


def die_on_exception(func):
    """Decoration to exit() the process when there's an unhandled exception.
    """

    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            traceback.print_exc()
            exit(1)

    return wrapper


class RemapperTrayIcon(TaskTrayIcon):
    def __init__(self, name, icon_path):
        super().__init__(name, icon_path)

    def _add_menu_items(self, menu):
        item = gtk.MenuItem(f'Restart {self.name}')
        item.connect('activate', self.restart)
        menu.append(item)

        super()._add_menu_items(menu)

    def restart(self, source):
        call_at_exists()
        os.execv(sys.argv[0], sys.argv)


class DoneEvent(Exception):
    pass


class BaseRemapper():
    uinput: SyncedUinput

    __devices: Dict[str, Tuple[evdev.InputDevice, int]]
    __orig_key_states: Dict[int, int] = collections.defaultdict(int)
    __udev_monitor: Optional[TextIO]

    def __init__(self,
                 remapper_name: str,
                 remapper_icon: str,
                 device_name_regex: str,
                 *,
                 id_regex='',
                 match_non_keyboards=False,
                 grab_devices=True,
                 write_to_uinput=True,
                 uinput_events: Optional[Dict[int, Iterable[int]]] = None,
                 global_lock_name: str = MAIN_FILE_NANE,
                 uinput_device_name_suffix: str = "-" + MAIN_FILE_NANE,
                 enable_debug=False,
                 force_quiet=False):
        self.remapper_name = remapper_name
        self.remapper_icon = remapper_icon

        self.device_name_regex = device_name_regex
        self.id_regex = id_regex
        self.match_non_keyboards = match_non_keyboards
        self.grab_devices = grab_devices
        self.write_to_uinput = write_to_uinput
        self.uinput_events = uinput_events
        self.global_lock_name = global_lock_name
        self.uinput_device_name_suffix = uinput_device_name_suffix
        self.enable_debug = enable_debug
        self.force_quiet = force_quiet

        self.__notification = notify2.Notification(remapper_name, '')
        self.__notification.set_urgency(notify2.URGENCY_NORMAL)
        self.__devices = {}
        self.tray_icon = RemapperTrayIcon(self.remapper_name, self.remapper_icon)
        self.__refresh_scheduled = False
        self.__modifier_char_validator = re.compile('''[^ascw]''')
        self.__extended_modifier_char_validator = re.compile('''[^ascwes]''')

        self.__lock = threading.RLock()

    def show_notification(self, message: str, timeout_ms=3000) -> None:
        if self.enable_debug: print(message)
        self.__notification.update(self.remapper_name, message)
        self.__notification.set_timeout(timeout_ms)
        self.__notification.show()

    def uinput_events_add_all_keys_events(self, uinput_events:Optional[Dict[int, Iterable[int]]]=None) \
            -> Dict[int, Iterable[int]]:
        """
        Add all KEY_ and BTN_ events to a uinput event dictionary.
        """
        if uinput_events is None:
            uinput_events = {}
        uinput_events[ecodes.EV_KEY] = ecodes.keys.keys()
        return uinput_events

    def on_initialize(self):
        pass

    def on_device_detected(self, devices: List[evdev.InputDevice]):
        self.show_notification('Device connected:\n'
                               + '\n'.join('- ' + d.name for d in devices))

    def on_device_not_found(self):
        self.show_notification('Device not found')

    def on_device_lost(self):
        self.show_notification('Device lost')

    def on_exception(self, exception: BaseException):
        self.show_notification('Device lost')

    def on_stop(self):
        self.show_notification('Closing...')

    def get_active_window(self) -> Tuple[str, str, str]:  # title, class_group_name, class_instance_name
        # Note: use `wmctrl -lx` to list window classes.
        # Example: For the following window,
        # 0x03a00007  0 www.amazon.co.jp__kindle-dbs_library_manga.Google-chrome  x1c7u マンガ本棚
        # This method returns:
        # ('マンガ本棚', 'www.amazon.co.jp__kindle-dbs_library_manga', 'Google-chrome')
        #
        # See https://lazka.github.io/pgi-docs/Wnck-3.0/classes/Window.html for wnck
        screen = wnck.Screen.get_default()
        screen.force_update()
        w = screen.get_active_window()

        return (w.get_name(), w.get_class_group_name(), w.get_class_instance_name())

    def __start_udev_monitor(self):
        pr, pw = os.pipe()
        os.set_blocking(pr, False)
        reader = os.fdopen(pr)
        writer = os.fdopen(pw, 'w')

        def run():
            try:
                context = pyudev.Context()
                monitor = pyudev.Monitor.from_netlink(context)
                monitor.filter_by(subsystem='input')
                if debug: print('Device monitor started.')

                for action, device in monitor:
                    if debug: print(f'udev: action={action} {device}')
                    writer.writelines(action)
                    writer.flush()
            except:
                traceback.print_exc()
                exit(1)

        th = threading.Thread(target=run)
        th.setDaemon(True)
        th.start()

        self.__udev_monitor = reader

    def __release_devices(self):
        if not self.__devices:
            return
        if debug: print('# Releasing devices...')
        for path, t in self.__devices.items():
            if debug: print(f'  Releasing {path}')
            glib.source_remove(t[1])
            try:
                t[0].ungrab()
            except IOError:
                pass  # ignore
            try:
                t[0].close()
            except IOError:
                pass  # ignore

    def __open_devices(self):
        self.__release_devices()

        if debug: print('# Detecting devices...')

        device_name_matcher = re.compile(self.device_name_regex)
        id_matcher = re.compile(self.id_regex, re.IGNORECASE)

        for device in [evdev.InputDevice(path) for path in sorted(evdev.list_devices())]:
            # Ignore other key_remapper uinput devices.
            if device.name.startswith(UINPUT_DEVICE_NAME):
                continue

            id_info = f'v{device.info.vendor :04x} p{device.info.product :04x}'
            if debug:
                print(f'Device: {device} / {id_info}')
                print(f'  Capabilities: {device.capabilities(verbose=True)}')

            # Reject the ones that don't match the name filter.
            if not (device_name_matcher.search(device.name) and id_matcher.search(id_info)):
                if debug: print(f'  Skipping {device.name}')
                continue

            add = False
            caps = device.capabilities()
            if self.match_non_keyboards:
                add = True
            else:
                for c in caps.keys():
                    if c not in (e.EV_SYN, e.EV_KEY, e.EV_MSC, e.EV_LED, e.EV_REP):
                        add = False
                        break
                    if c == e.EV_KEY:
                        add = True

            if add and self.grab_devices:
                try:
                    device.grab()
                except IOError:
                    if not quiet: print(f'Unable to grab {device.path}', file=sys.stderr)

            if add:
                if debug: print(f"Using device: {device}")
            else:
                try:
                    device.close()
                except IOError:
                    pass
                continue

            tag = glib.io_add_watch(device, glib.IO_IN, self.__on_input_event)
            self.__devices[device.path] = [device, tag]

        # We just opened the devices, so drain all udev monitor events.
        if self.__udev_monitor:
            self.__udev_monitor.readlines()

        if self.__devices:
            self.on_device_detected([t[0] for t in self.__devices.values()])
        else:
            self.on_device_not_found()

    def __schedule_refresh_devices(self):
        if self.__refresh_scheduled:
            return
        self.__refresh_scheduled = True

        def call_refresh():
            self.__refresh_scheduled = False
            self.on_device_lost()
            self.__open_devices()
            return False

        # Re-open the devices, but before that, wait a bit because udev sends multiple add events in a row.
        # Also randomize the delay to avoid multiple instances of keymapper
        # clients don't race.
        glib.timeout_add(random.uniform(1, 2) * 1000, call_refresh)

    def __on_udev_event(self, udev_monitor: TextIO, condition):
        refresh_devices = False
        for event in udev_monitor.readlines():  # drain all the events
            if event in ['add', 'remove']:
                if debug:
                    print('# Udev device change detected.')
                    sys.stdout.flush()
                refresh_devices = True

        if refresh_devices:
            self.uinput.reset()
            self.__schedule_refresh_devices()

        return True

    def __on_input_event(self, device: evdev.InputDevice, condition):
        events = []
        for ev in device.read():
            events.append(ev)

        events = self.on_preprocess_events(device, events)

        for ev in events:
            with self.__lock:
                self.__orig_key_states[ev.code] = ev.value

        if debug:
            for ev in events:
                print(f'-> Event: {ev}')

        try:
            self.on_handle_events(device, events)
        except:
            traceback.print_exc()
            exit(1)

        return True

    def send_ievent(self, event: evdev.InputEvent) -> None:
        self.send_event(event.type, event.code, event.value)

    def send_event(self, type: int, key: int, value: int) -> None:
        with self.__lock:
            self.uinput.write(evdev.InputEvent(0, 0, type, key, value))

    def send_key_event(self, key: int, value: int) -> None:
        with self.__lock:
            self.uinput.write(evdev.InputEvent(0, 0, ecodes.EV_KEY, key, value))

    def send_key_events(self, *keys: Tuple[int, int]) -> None:
        with self.__lock:
            for k in keys:
                self.uinput.write(evdev.InputEvent(0, 0, ecodes.EV_KEY, k[0], k[1]))

    def press_key(self, key: int, modifiers:str=None, *, reset_all_keys=True, done=False) -> None:
        with self.__lock:
            # If modifier is "*", don't reset the key state, to allow combining with other modifiers.
            if modifiers == "*":
                reset_all_keys = False
                modifiers = ""

            # Release all already-pressed modifier keys by default.
            if reset_all_keys:
                self.reset_all_keys()

            if modifiers is None:
                modifiers = ""

            if self.__modifier_char_validator.search(modifiers):
                raise ValueError(f'`modifiers` "f{modifiers}" contains unexpected char. Expected a, c, s and w.')

            # TODO Maybe remember the previous state and restore, rather than the current "reset -> press modifilers
            # and later release them all" strategy.
            alt = 'a' in modifiers
            ctrl = 'c' in modifiers
            shift = 's' in modifiers
            win = 'w' in modifiers

            if alt: self.send_key_event(ecodes.KEY_LEFTALT, 1)
            if ctrl: self.send_key_event(ecodes.KEY_LEFTCTRL, 1)
            if shift: self.send_key_event(ecodes.KEY_LEFTSHIFT, 1)
            if win: self.send_key_event(ecodes.KEY_LEFTMETA, 1)
            self.send_key_event(key, 1)
            self.send_key_event(key, 0)
            if win: self.send_key_event(ecodes.KEY_LEFTMETA, 0)
            if shift: self.send_key_event(ecodes.KEY_LEFTSHIFT, 0)
            if ctrl: self.send_key_event(ecodes.KEY_LEFTCTRL, 0)
            if alt: self.send_key_event(ecodes.KEY_LEFTALT, 0)

            if done:
                raise DoneEvent()

    def reset_all_keys(self) -> None:
        self.uinput.reset()

    def get_out_key_state(self, key: int) -> int:
        return self.uinput.get_key_state(key)

    def get_in_key_state(self, key: int) -> int:
        with self.__lock:
            return self.__orig_key_states[key]

    def is_key_pressed(self, key: int) -> bool:
        with self.__lock:
            return self.get_in_key_state(key) > 0

    def check_modifiers(self, modifiers: str, *, ignore_other_modifiers=False):
        with self.__lock:
            if modifiers is None:
                modifiers = ""
            elif self.__extended_modifier_char_validator.search(modifiers):
                raise ValueError(f'`modifiers` "f{modifiers}" contains unexpected char. Expected a, c, s, w, e and p.')

            alt = 'a' in modifiers
            ctrl = 'c' in modifiers
            shift = 's' in modifiers
            win = 'w' in modifiers
            esc = 'e' in modifiers  # Allow ESC to be used as a modifier
            caps = 'p' in modifiers # Allow CAPS to be used as a modifier

            if self.is_alt_pressed() != alt and (alt or not ignore_other_modifiers):
                return False

            if self.is_ctrl_pressed() != ctrl and (ctrl or not ignore_other_modifiers):
                return False

            if self.is_shift_pressed() != shift and (shift or not ignore_other_modifiers):
                return False

            if self.is_win_pressed() != win and (win or not ignore_other_modifiers):
                return False

            if self.is_esc_pressed() != esc and (esc or not ignore_other_modifiers):
                return False

            if self.is_caps_pressed() != caps and (caps or not ignore_other_modifiers):
                return False

        return True

    def is_alt_pressed(self):
        with self.__lock:
            return self.is_key_pressed(ecodes.KEY_LEFTALT) or self.is_key_pressed(ecodes.KEY_RIGHTALT)

    def is_ctrl_pressed(self):
        with self.__lock:
            return self.is_key_pressed(ecodes.KEY_LEFTCTRL) or self.is_key_pressed(ecodes.KEY_RIGHTCTRL)

    def is_shift_pressed(self):
        with self.__lock:
            return self.is_key_pressed(ecodes.KEY_LEFTSHIFT) or self.is_key_pressed(ecodes.KEY_RIGHTSHIFT)

    def is_win_pressed(self):
        with self.__lock:
            return self.is_key_pressed(ecodes.KEY_LEFTMETA) or self.is_key_pressed(ecodes.KEY_RIGHTMETA)

    def is_esc_pressed(self):
        with self.__lock:
            return self.is_key_pressed(ecodes.KEY_ESC)

    def is_caps_pressed(self):
        with self.__lock:
            return self.is_key_pressed(ecodes.KEY_CAPSLOCK)

    def matches_key(self,
                    ev: evdev.InputEvent,
                    expected_keys: Union[int, Iterable[int]],
                    expected_values: Union[int, Iterable[int]],
                    expected_modifiers: Optional[str] = None,
                    predecate: Callable[[], bool] = None,
                    *, ignore_other_modifiers=False) -> bool:
        with self.__lock:
            if isinstance(expected_keys, int):
                if ev.code != expected_keys:
                    return False
            elif isinstance(expected_keys, Iterable):
                if ev.code not in expected_keys:
                    return False
            else:
                raise ValueError(f'Invalid type of expected_keys: actual={expected_keys}')

            if isinstance(expected_values, int):
                if ev.value != expected_values:
                    return False
            elif isinstance(expected_values, Iterable):
                if ev.value not in expected_values:
                    return False
            else:
                raise ValueError(f'Invalid type of expected_values: actual={expected_values}')

            # If expected_modifiers is non-null, make sure these keys are pressed.
            if expected_modifiers:
                if not self.check_modifiers(expected_modifiers, ignore_other_modifiers=ignore_other_modifiers):
                    return False

            if predecate and not predecate():
                return False

            return True

    def on_preprocess_events(self, device: evdev.InputDevice, events: List[evdev.InputEvent]) -> List[evdev.InputEvent]:
        """
        Called before the incoming inputs are stored in the internal states used by get_in_key_state() and
        other is_*() methods.
        """
        return events

    def on_handle_events(self, device: evdev.InputDevice, events: List[evdev.InputEvent]) -> None:
        try:
            for event in events:
                try:
                    self.on_handle_event(device, event)
                except DoneEvent:
                    pass
        except DoneEvent:
            pass

    def on_handle_event(self, device: evdev.InputDevice, event: evdev.InputEvent) -> None:
        pass

    def __parse_args(self, args):
        parser = argparse.ArgumentParser(description=self.remapper_name)
        parser.add_argument('-m', '--match-device-name', metavar='D', default=self.device_name_regex,
                            help='Select by device name using this regex. Use evtest(1) to list device names')
        parser.add_argument('-i', '--match-id', metavar='D', default=self.id_regex,
                            help='Select by vendor/product ID, in "vXXXX pXXXX" format, using this regex')
        parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')
        parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')

        self.on_init_arguments(parser)

        args = parser.parse_args(args)

        self.device_name_regex = args.match_device_name
        self.id_regex = args.match_id
        self.enable_debug = args.debug
        self.force_quiet = args.quiet

        global debug, quiet
        debug = self.enable_debug
        quiet = self.force_quiet

        self.on_arguments_parsed(args)

    def on_init_arguments(self, parser):
        pass

    def on_arguments_parsed(self, args):
        pass

    def new_uintput(self, name_suffix: str, uinput_events=Optional[Dict[int, Iterable[int]]]) -> SyncedUinput:
        # Create a new uinput device with arbitrary events.
        uinput_name = UINPUT_DEVICE_NAME + self.uinput_device_name_suffix + name_suffix
        uinput = UInput(name=uinput_name, events=uinput_events)
        if debug: print(f'# New uinput device name: {uinput_name}')
        uinput = SyncedUinput(uinput)
        add_at_exit(uinput.close)
        return uinput

    def new_keyboard_uinput(self, name_suffix: str) -> SyncedUinput:
        # Create a new uinput device with keyboard events.
        return self.new_uintput(name_suffix, None)

    def new_mouse_uinput(self, name_suffix: str) -> SyncedUinput:
        # Create a new uinput device with mouse events.
        events = {}
        events[ecodes.EV_KEY] = (ecodes.BTN_LEFT, ecodes.BTN_MIDDLE, ecodes.BTN_RIGHT, ecodes.BTN_SIDE,
                                 ecodes.BTN_EXTRA, ecodes.BTN_BACK, ecodes.BTN_FORWARD)
        events[ecodes.EV_REL] = (ecodes.REL_X, ecodes.REL_Y,
                                 ecodes.REL_WHEEL, ecodes.REL_HWHEEL,
                                 ecodes.REL_WHEEL_HI_RES, ecodes.REL_HWHEEL_HI_RES,
                                 )
        return self.new_uintput(name_suffix, events)

    def main(self, args):
        ensure_singleton(self.global_lock_name)
        notify2.init(self.remapper_name)

        self.__parse_args(args)

        if self.write_to_uinput:
            # Create our /dev/uinput device.
            self.uinput = self.new_uintput("", self.uinput_events)
        self.__start_udev_monitor()
        glib.io_add_watch(self.__udev_monitor, glib.IO_IN, self.__on_udev_event)

        self.on_initialize()

        self.__open_devices()
        add_at_exit(self.__release_devices)

        try:
            gtk.main()
        finally:
            self.reset_all_keys()

        exit(0)


def _main(args, description="key remapper test"):
    pass

if __name__ == '__main__':
    _main(sys.argv[1:])
