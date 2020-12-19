# key_remapper.py

Python framework for creating flexible key-remapping for Linux.
(In attempt to replicate AHK-like flexible remapping.)

## Prerequisite

```
pip3 install evdev notify2
```
... And more?

## What It Provides

It provides the following features:
- "Steal" input events from keyboards,
  and optionally pointing devices if `match_non_keyboards` is set to `True`.
  (See [trackpoint-speedup.py](trackpoint-speedup.py) as an example of tweaking a pointing device.)

  "Steal" means all the events from the target devices _will be ignored unless you forward
  them to uinput_ using the following feature.
  
  Optionally, pass `False` to `grab_devices` to avoid this stealing behavior, which still
  allows you to sniff into the input events.

- Synthesize input device events (key presses, mouse moves, etc) via uinput.

- `SimpleRemapper.get_active_window()` returns the information about the active window.

- Simple tasktray icon.

- Unlike AHK, key_remapper can operate only on specific devices, specified by names or vendor/product IDs, using
  regexes. It allows to handle different devices in different ways. (e.g. use different mappings for diffetent
  devices.)

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