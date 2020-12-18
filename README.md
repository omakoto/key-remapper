# key_remapper.py

Python framework for AHK like flexible key-remapping for Linux.

## Prerequisite

```
pip3 install evdev notify2
```
... And more?

## What It Provides

It provides the following features:
- "Steal" input events from keyboards,
  and optionally pointing devices if `match_non_keyboards` is set to `True`.

  "Steal" means all the events from the target devices _will be ignored unless you forward
  them to uinput_ using the following feature.
  
  Optionally, pass `False` to `grab_devices` to avoid this stealing behavior, which still
  allows you to sniff into the input events.

- Synthesize input device events (key presses, mouse moves, etc) via uinput.
- `SimpleRemapper.get_active_window()` returns the information about the active window.
- Simple tasktray icon.


## Samples
 
Note all the following samples will _remap only certain kinds of keyboards_ specified
by the regex `DEFAULT_DEVICE_NAME` in them. To target all (keyboard) devices, start them
with `-m ''`.

 - [main-keyboard-remapper.py](main-keyboard-remapper.py) for the following 3 keyboards:
   - The Thinkpad Internal keyboard (at least for X1 carbon gen7 and P1 gen2)
   - Topre Realforce
   - https://www.amazon.com/gp/product/B00EZ4A2OQ

 - [shortcut-remote-remapper.py](shortcut-remote-remapper.py) for https://www.amazon.com/gp/product/B01NC2LEYP