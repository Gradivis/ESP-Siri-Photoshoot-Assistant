# Shoot box POC: Wi-Fi HTTP commands -> Neewer lights over BLE.
# http://shootbox.local/<command>[?l=1|2|all&b=&h=&s=&k=], e.g. /red, /blue?b=50&l=2, /off.
import network, socket, time
import secrets
from neewer import Bus

COLOURS = {  # hue 0-360
    "red": 0, "orange": 25, "amber": 40, "yellow": 55, "green": 120, "teal": 170,
    "cyan": 185, "blue": 230, "indigo": 255, "purple": 275, "violet": 265,
    "magenta": 305, "pink": 325,
}
SCENES = {  # name -> (hue, sat, bri)
    "cyberpunk": (305, 100, 60),
    "moody": (230, 100, 15),
}


def wifi():
    network.hostname("shootbox")
    w = network.WLAN(network.STA_IF)
    w.active(True)
    if not w.isconnected():
        w.connect(secrets.SSID, secrets.PASSWORD)
        for _ in range(60):
            if w.isconnected():
                break
            time.sleep_ms(250)
    print("wifi", w.isconnected(), w.ifconfig()[0])
    return w


NUMBER_WORDS = {
    "one": 1, "five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100, "full": 100, "max": 100, "maximum": 100,
    "half": 50, "low": 10, "minimum": 1,
}
COMMANDS = ("on", "off", "white", "color", "status", "brighter", "dimmer", "brightness",
            "shoot", "stop", "next", "scan")

# Two-light looks: name -> (light 1, light 2). Each light is ("h", hue, sat, rel) or ("k", kelvin, rel),
# where rel is brightness relative to the master level (100 = master).
LOOKS = [
    ("noir", ("h", 320, 100, 100), ("h", 190, 100, 55)),
    ("reversenoir", ("h", 190, 100, 100), ("h", 320, 100, 55)),
    ("sunset", ("h", 30, 100, 100), ("h", 275, 100, 60)),
    ("bloodmoon", ("h", 0, 100, 100), ("h", 235, 100, 35)),
    ("goldenhour", ("k", 3200, 100), ("h", 25, 100, 50)),
    ("interrogation", ("k", 5600, 100), ("h", 190, 100, 20)),
    ("toxic", ("h", 120, 100, 100), ("h", 305, 100, 50)),
    ("ocean", ("h", 175, 100, 90), ("h", 225, 100, 100)),
    ("ember", ("h", 5, 100, 100), ("h", 30, 100, 70)),
    ("vaporwave", ("h", 330, 90, 90), ("h", 170, 90, 90)),
    ("royal", ("h", 275, 100, 100), ("h", 40, 100, 45)),
    ("blockbuster", ("h", 25, 100, 100), ("h", 220, 100, 100)),
    ("redroom", ("h", 0, 100, 100), ("h", 0, 100, 30)),
    ("ultraviolet", ("h", 265, 100, 100), ("h", 255, 100, 40)),
    ("studio", ("k", 5000, 100), ("k", 5000, 50)),
    ("acid", ("h", 55, 100, 100), ("h", 280, 100, 60)),
    ("arctic", ("k", 5600, 70), ("h", 185, 100, 100)),
    ("hellfire", ("h", 0, 100, 100), ("h", 40, 100, 100)),
    ("cyberpunk", ("h", 325, 100, 100), ("h", 230, 100, 80)),
    ("midnight", ("h", 230, 100, 60), ("h", 250, 100, 25)),
]
LOOK_NAMES = [l[0] for l in LOOKS]
shoot = {"active": False, "master": 50, "idx": 0, "end": 0, "next": 0, "secs": 30}
states = []  # one dict per light, filled after scan


def unquote(s):
    out, i = bytearray(), 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            out.append(int(s[i + 1:i + 3], 16))
            i += 3
        else:
            out.append(32 if s[i] == "+" else ord(s[i]))
            i += 1
    return out.decode()


def parse(path):
    # Dictated input arrives as e.g. "/Blue 80%." or "/make%20it%20dimmer": first known word wins,
    # and any number (digits or words like "fifty") is the brightness.
    route, _, q = path.partition("?")
    args = {}
    for kv in q.split("&"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            args[k] = v
    text = unquote(route).lower()
    words = "".join(ch if (ch.isalpha() or ch.isdigit()) else " " for ch in text).split()
    cmd = None
    for w in words:
        if w.isdigit() and "b" not in args:
            args["b"] = w
        elif w in NUMBER_WORDS and "b" not in args:
            args["b"] = str(NUMBER_WORDS[w])
        elif cmd is None and (w in COLOURS or w in SCENES or w in COMMANDS or w in LOOK_NAMES):
            cmd = w
    if cmd is None:
        cmd = "brightness" if "b" in args else (words[0] if words else "")
    return cmd, args


def new_state():
    return {"mode": "hsi", "h": 0, "s": 100, "b": 30, "k": 5600, "on": True}


def apply(light, st):
    st["b"] = max(1, min(100, st["b"]))
    st["on"] = True
    if st["mode"] == "cct":
        return light.power(True) and light.cct(st["b"], st["k"])
    return light.power(True) and light.hsi(st["h"], st["s"], st["b"])


def handle_one(light, st, route, args):
    if "b" in args:
        st["b"] = int(args["b"])
    if route == "on":
        st["on"] = True
        return light.power(True)
    if route == "off":
        st["on"] = False
        return light.power(False)
    if route in COLOURS:
        st.update(mode="hsi", h=COLOURS[route], s=int(args.get("s", 100)))
    elif route in SCENES:
        h, s, b = SCENES[route]
        st.update(mode="hsi", h=h, s=s)
        if "b" not in args:
            st["b"] = b
    elif route == "white":
        st.update(mode="cct", k=int(args.get("k", st["k"])))
    elif route == "color":
        st.update(mode="hsi", h=int(args.get("h", st["h"])), s=int(args.get("s", st["s"])))
    elif route == "brighter":
        st["b"] += 20
    elif route == "dimmer":
        st["b"] -= 20
    elif route != "brightness":
        return None
    return apply(light, st)


def targets(args, lights):
    l = args.get("l", "all")
    if l == "all":
        return list(range(len(lights)))
    return [int(x) - 1 for x in l.split(",") if x.isdigit() and 0 < int(x) <= len(lights)]


def describe(i, light, st):
    if not st["on"]:
        what = "off"
    elif st["mode"] == "cct":
        what = "white %dK %d%%" % (st["k"], st["b"])
    else:
        what = "hue %d sat %d %d%%" % (st["h"], st["s"], st["b"])
    return "light %d (%s) %s: %s" % (i + 1, light.mac[-5:], "connected" if light.handle else "NOT connected", what)


def show_look(lights, idx, master):
    name, *specs = LOOKS[idx % len(LOOKS)]
    ok = True
    for i, spec in enumerate(specs[:len(lights)]):
        st = states[i]
        if spec[0] == "k":
            st.update(mode="cct", k=spec[1], b=max(1, master * spec[2] // 100))
        else:
            st.update(mode="hsi", h=spec[1], s=spec[2], b=max(1, master * spec[3] // 100))
        ok = apply(lights[i], st) and ok
    return name, ok


def shoot_status():
    if not shoot["active"]:
        return "shoot mode: off"
    left = time.ticks_diff(shoot["end"], time.ticks_ms()) // 1000
    return "shoot mode: on, look %d/%d '%s', master %d%%, %dm%02ds left" % (
        shoot["idx"] % len(LOOKS) + 1, len(LOOKS), LOOK_NAMES[shoot["idx"] % len(LOOKS)],
        shoot["master"], left // 60, left % 60)


def command(bus, lights, route, args):
    """Returns (ok, message, lights)."""
    if route == "scan" or not lights:
        lights = bus.scan()  # finds lights switched on after boot; reconnects dropped ones
        while len(states) < len(lights):
            states.append(new_state())
    if route == "scan":
        route = "status"
    if route == "shoot":
        shoot.update(active=True, master=int(args.get("b", 50)), idx=0,
                     secs=int(args.get("secs", 30)))
        shoot["end"] = time.ticks_add(time.ticks_ms(), int(args.get("mins", 10)) * 60000)
        shoot["next"] = time.ticks_add(time.ticks_ms(), shoot["secs"] * 1000)
        show_look(lights, 0, shoot["master"])
        return True, shoot_status(), lights
    if route == "stop":
        shoot["active"] = False
        return True, shoot_status() + " (lights hold the last look)", lights
    if route == "next" and shoot["active"]:
        shoot["idx"] += 1
        shoot["next"] = time.ticks_add(time.ticks_ms(), shoot["secs"] * 1000)
        show_look(lights, shoot["idx"], shoot["master"])
        return True, shoot_status(), lights
    if route in LOOK_NAMES:
        master = int(args.get("b", shoot["master"]))
        name, ok = show_look(lights, LOOK_NAMES.index(route), master)
        return ok, "look '%s' at master %d%%" % (name, master), lights
    if shoot["active"] and route in ("brightness", "brighter", "dimmer"):
        if route == "brightness":
            shoot["master"] = int(args.get("b", shoot["master"]))
        else:
            shoot["master"] += 20 if route == "brighter" else -20
        shoot["master"] = max(1, min(100, shoot["master"]))
        show_look(lights, shoot["idx"], shoot["master"])
        return True, shoot_status(), lights
    if route in ("", "status"):
        body = "\n".join(describe(i, l, states[i]) for i, l in enumerate(lights)) or "no lights found"
        return True, body + "\n" + shoot_status(), lights
    if route == "off":
        shoot["active"] = False
    ts = targets(args, lights)
    results = [handle_one(lights[i], states[i], route, args) for i in ts]
    if not results or None in results:
        return False, "unknown command or light", lights
    return all(results), "\n".join(describe(i, lights[i], states[i]) for i in ts), lights


def tick(lights):
    if not shoot["active"]:
        return
    now = time.ticks_ms()
    if time.ticks_diff(now, shoot["end"]) >= 0:
        shoot["active"] = False
        print("shoot mode finished")
        return
    if time.ticks_diff(now, shoot["next"]) >= 0:
        shoot["idx"] += 1
        shoot["next"] = time.ticks_add(now, shoot["secs"] * 1000)
        print("look", show_look(lights, shoot["idx"], shoot["master"]))


def serve():
    bus = Bus()
    lights = bus.scan()
    while len(states) < len(lights):
        states.append(new_state())
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 80))
    s.listen(2)
    s.settimeout(0.5)
    while True:
        tick(lights)
        try:
            c, _ = s.accept()
        except OSError:
            continue
        try:
            c.settimeout(3)
            line = c.recv(512).split(b"\r\n", 1)[0].decode()
            path = line.split(" ")[1] if " " in line else "/"
            route, args = parse(path)
            ok, msg, lights = command(bus, lights, route, args)
            c.send(b"HTTP/1.0 %d OK\r\nContent-Type: text/plain\r\n\r\n%s\n" % (200 if ok else 500, msg.encode()))
            print(path, msg)
        except Exception as e:
            print("err", e)
        finally:
            c.close()


wifi()
serve()
