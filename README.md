# key_remapper.py

Python framework for creating flexible key-remapping for Linux.
(In attempt to replicate AHK-like flexible remapping.)

## Prerequisite

### Being able to `/dev/uinput`

- See https://stackoverflow.com/questions/11939255/writing-to-dev-uinput-on-ubuntu-12-04.

- You may need to do the `/etc/modules-load.d/uinput.conf` trick in
https://github.com/chrippa/ds4drv/issues/93#issuecomment-265300511 as well.

### Python modules

```
pip3 install evdev notify2
```
... and probably some more modules for GTK etc?

## What It Provides

At a high level, it allows to "steal" input events from specific devices
(keyboards, pointing devices, etc) using evdev, modify them and inject using `/dev/uinput`.

- Unlike AHK, key_remapper can operate only on specific devices, specified by names or vendor/product IDs, using
  regexes. It allows to handle different devices in different ways. (e.g. use different mappings for diffetent
  devices.)

- By default, it ignores all non-keyboard input devices.
  Pass `True` to `match_non_keyboards` to use non-keyboard devices too.
  See [trackpoint-speedup.py](trackpoint-speedup.py) as an example of
  tweaking pointing device events.

- Optionally, pass `False` to `grab_devices` to avoid this stealing behavior, which still
  allows you to sniff into the input events.

- Use `SimpleRemapper.get_active_window()` returns the information about the active window
  to change behavior depending on the current window.

## Samples
 
Note: all the following samples will _remap only certain kinds of keyboards_ specified
by the regex `DEFAULT_DEVICE_NAME` in them. To target all (keyboard) devices, start them
with `-m ''`. In order to distinguish different devices with the same name,
use the `-i` option.

 - [main-keyboard-remapper.py](main-keyboard-remapper.py) for the following 3 keyboards:
   - The Thinkpad Internal keyboard (at least for X1 carbon gen7 and P1 gen2)
   - Topre Realforce
   - https://www.amazon.com/gp/product/B00EZ4A2OQ

 - [shortcut-remote-remapper.py](shortcut-remote-remapper.py) for https://www.amazon.com/gp/product/B01NC2LEYP
 - [trackpoint-speedup.py](trackpoint-speedup.py) Speed up Thinkpad trackpoint.
 
 ## See Also
 
 - [python-evdev](https://python-evdev.readthedocs.io/en/latest/)
 