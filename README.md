# key_remapper.py

Python framework for creating flexible key-remapping for Linux.
(In attempt to replicate AHK-like flexible remapping.)

## Project Moving

I'm rewriting it in Rust: https://github.com/omakoto/keyremapper-rs

## Prerequisite

### Access to `/dev/input/*` and `/dev/uinput`

```sh
# Add self to the input and uinput groups
sudo usermod -aG input $USER 
sudo groupadd uinput
sudo usermod -aG uinput $USER

# See https://github.com/chrippa/ds4drv/issues/93
echo 'KERNEL=="uinput", SUBSYSTEM=="misc", MODE="0660", GROUP="uinput"' | sudo tee /etc/udev/rules.d/90-uinput.rules

# This seems to be needed because uinput isn't compiled as a loadable module these days.
echo uinput | sudo tee /etc/modules-load.d/uinput.conf
```

Then reboot.

See also:
- https://stackoverflow.com/questions/11939255/writing-to-dev-uinput-on-ubuntu-12-04.
- https://github.com/chrippa/ds4drv/issues/93#issuecomment-265300511

### Python3 and modules

```sh
sudo apt install -y python3 python3-pip
sudo pip3 install evdev notify2
```

You may need gtk/glib etc modules too but I forgot how I installed them.

## What It Provides

At a high level, it allows to "steal" input events from specific devices
(keyboards, pointing devices, etc) using evdev, modify them and inject using `/dev/uinput`.

- Unlike AHK, key_remapper can operate only on specific devices, specified by names or vendor/product IDs, using
  regexes. It allows to handle different devices in different ways. e.g. use different mappings for diffetent
  devices.

- By default, it ignores all non-keyboard input devices.
  Pass `True` to `match_non_keyboards` to use non-keyboard devices too.
  See [trackpoint-speedup.py](trackpoint-speedup.py) as an example of
  tweaking pointing device events.

- Optionally, pass `False` to `grab_devices` to let original events also go through,
  which still allows you to just sniff into the input events.

- Use `SimpleRemapper.get_active_window()` returns the information about the active window
  to change behavior depending on the current window.

## Samples
 
Note: all the following samples will _remap only certain kinds of keyboards_ specified
by the regex `DEFAULT_DEVICE_NAME` in them. To target all (keyboard) devices, start them
with `-m ''`. In order to distinguish different devices with the same name,
use the `-i` option.

- [main-keyboard-remapper.py](main-keyboard-remapper.py)
  - For the following 3 keyboards:
    - The Thinkpad Internal keyboard (at least for X1 carbon gen7 and P1 gen2)
    - Topre Realforce
    - https://www.amazon.com/gp/product/B00EZ4A2OQ
  - Adds various shortcuts using `ESC` and `Capslock`.
  - Creates an extra uinput device to inject mouse wheel events.
    e.g. `ESC` + `H`, `J`, `K` and `L` for virtucal and horizontal scroll.

- [shortcut-remote-remapper.py](shortcut-remote-remapper.py) for https://www.amazon.com/gp/product/B01NC2LEYP
- [trackpoint-speedup.py](trackpoint-speedup.py) Speed up Thinkpad trackpoint.
   I can never figure out how to easily do it.

## See Also

- [python-evdev](https://python-evdev.readthedocs.io/en/latest/) 
