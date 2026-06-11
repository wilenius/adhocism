---
title: "Running Norns on a desktop computer – misc notes"
tags: 
- norns
- supercollider
categories: 
date: 2026-06-08
lastMod: 2026-06-08
---
### Connecting a REPL / editor

**maiden-repl (CLI):** `build/maiden-repl/maiden-repl` — defaults to
`ws4://127.0.0.1:5555/` (matron) and `:5556/` (sclang). **Tab** cycles
pages (matron ⇄ sc); **Shift+Tab** also switches. The matron page takes raw
Lua; the sc page takes SuperCollider (it sends sclang's ESC evaluate
delimiter for you).

**maiden web app:** separate Go binary/release; serves the editor on `:5000`
and connects out to 5555/5556.

### Loading scripts and driving params from the REPL

On the **matron** page (raw Lua):

```lua
norns.script.load("code/hello/hello.lua")  -- path is relative to ~/dust/
norns.script.load()                         -- reload current script

params:print()                              -- enumerate params (index/id = value)
params:get("hello_value")                   -- read by id (or numeric index)
params:set("hello_value", 42)               -- set by id
params:delta("hello_value", 1)              -- relative change
params.count                                -- number of params
```

> Gotcha: a script's `init()` (where it adds its params) only runs *after*
> SuperCollider acks — `Script.run` calls `engine.load("None", Script.init)`
> and `Script.init` is the ack callback. So if SC failed, no params exist and
> `params:set("...")` errors with `invalid paramset index`. Get the handshake
> working first.

### Ports / SuperCollider handshake (for troubleshooting)

Defaults from `matron/src/args.cc` + `osc.cc`, and the SC side
(`sc/core/Crone.sc`):

| Port | Who listens | Used for |
|---|---|---|
| 57110 | scsynth | audio *server* (normal; **not** the handshake port) |
| **57120** | **sclang** | matron sends `/ready` + engine cmds here |
| **8888** | matron (`loc_port`) | sclang replies `/crone/ready` + reports here |
| 9999 | C++ crone | matron→crone audio/softcut commands |
| 10111 | matron (`remote_port`) | script-facing OSC (`osc.lua`) |

Quick diagnosis — with everything running, scan the UDP listeners:

```
ss -ulpn | grep -E ':(8888|9999|10111|5711[0-9]|5712[0-9]) '
```

You want `sclang` on `:57120` and `norns` on `:8888`. If sclang isn't on
57120 (something else grabbed it), either free it and restart sclang, or start
matron pointed at sclang's actual port: `build/norns/norns -e <langPort>`.
(matron flags: `-l` local port, `-e` ext/sclang port, `-c` crone port.) If
ports and start-order are correct but it still times out, sniff loopback OSC:
`sudo tcpdump -i lo -A -n 'udp port 57120 or udp port 8888'` and watch for
`/ready` (matron→57120) and `/crone/ready` (sclang→8888).

