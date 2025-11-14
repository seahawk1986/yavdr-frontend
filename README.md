# yavdr-frontend

This script controls the various programs that can be displayed on a yavdr-ansible installation.

## required packages on an Ubuntu system when using uv

 * libgirepository-2.0-dev
 * python3-all-dev

## settings

## systemd and dbus integration
```
Start arguments: [] -> response: []
start arguments: [] -> response: ['b', 's']
Stop arguments: [] -> response: ['b', 's']
stop arguments: [] -> response: ['b', 's']
Toggle arguments: [] -> response: ['b', 's']
toggle arguments: [] -> response: ['b', 's']
ToggleNoninteractive arguments: [] -> response: ['b', 's']
Switch arguments: [] -> response: ['b', 's']
Switchto arguments: ['s'] -> response: ['b']
switchto arguments: ['s'] -> response: ['b']
Switchbetween arguments: ['s', 's'] -> response: ['b']
SetNext arguments: ['s'] -> response: ['b']
SetDisplay arguments: ['s'] -> response: []
StartDesktop arguments: ['s'] -> response: ['b', 's']
SetNextFe arguments: ['s', 's', 's'] -> response: ['b']
Quit arguments: [] -> response: ['b']
ShutdownSuccessfull arguments: [] -> response: ['b']
```

## modus operandi
The `Controller` module manages the submodules for VDR-frontends and additional applications. Each submodule has to implement the `FrontendProtocol`.

### "normal" applications
