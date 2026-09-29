# Neewer BLE lights (standard protocol, e.g. RGB660 PRO), several at once.
# Protocol from NeewerLite-Python: write to 69400002-..., bytes [120, tag, len, *params, sum & 0xff].
import bluetooth, time

CHR = bluetooth.UUID('69400002-B5A3-F393-E0A9-E50E24DCCA99')
_CONNECT, _DISCONNECT, _SCAN_RESULT, _SCAN_DONE, _CHR_RESULT, _CHR_DONE = 7, 8, 5, 6, 11, 12


def _adv_name(adv):
    i = 0
    while i + 1 < len(adv):
        ln = adv[i]
        if ln == 0:
            break
        if adv[i + 1] in (8, 9):
            return bytes(adv[i + 2:i + 1 + ln]).decode('utf-8', 'ignore')
        i += 1 + ln
    return None


class Light:
    def __init__(self, bus, addr_type, addr, name):
        self.bus, self.addr_type, self.addr, self.name = bus, addr_type, addr, name
        self.conn = None
        self.handle = None

    @property
    def mac(self):
        return self.addr.hex(':')

    def connect(self):
        if self.conn is not None and self.handle is not None:
            return True
        for _ in range(3):
            self.bus.pending = self
            self.bus.done = False
            self.bus.ble.gap_connect(self.addr_type, self.addr)
            if self.bus.wait() and self.conn is not None:
                self.bus.ble.gattc_discover_characteristics(self.conn, 1, 0xffff)
                self.bus.wait()
                if self.handle:
                    return True
            try:
                self.bus.ble.gap_connect(None)
            except Exception:
                pass
            time.sleep_ms(300)
        return False

    def send(self, cmd):
        if not self.connect():
            return False
        self.bus.ble.gattc_write(self.conn, self.handle, bytes(cmd + [sum(cmd) & 0xff]), 0)
        time.sleep_ms(30)
        return True

    def power(self, on):
        return self.send([120, 129, 1, 1 if on else 2])

    def hsi(self, hue, sat=100, bri=30):
        return self.send([120, 134, 4, hue & 255, hue >> 8, sat, bri])

    def cct(self, bri=30, kelvin=5600):
        return self.send([120, 135, 2, bri, kelvin // 100, 50])


class Bus:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)
        self.lights = []
        self.found = {}
        self.pending = None
        self.done = False

    def _by_conn(self, conn):
        for l in self.lights:
            if l.conn == conn:
                return l

    def _irq(self, ev, data):
        if ev == _SCAN_RESULT:
            at, addr, _, _, adv = data
            name = _adv_name(adv)
            if name and name.upper().startswith('NEEWER'):
                self.found[bytes(addr)] = (at, name)
        elif ev == _SCAN_DONE:
            self.done = True
        elif ev == _CONNECT:
            if self.pending:
                self.pending.conn = data[0]
            self.done = True
        elif ev == _DISCONNECT:
            l = self._by_conn(data[0])
            if l:
                l.conn = None
                l.handle = None
            self.done = True
        elif ev == _CHR_RESULT:
            l = self._by_conn(data[0])
            if l and data[4] == CHR:
                l.handle = data[2]
        elif ev == _CHR_DONE:
            self.done = True

    def wait(self, t=4):
        s = time.ticks_ms()
        while not self.done and time.ticks_diff(time.ticks_ms(), s) < t * 1000:
            time.sleep_ms(20)
        ok = self.done
        self.done = False
        return ok

    def scan(self, ms=6000):
        self.done = False
        self.ble.gap_scan(ms, 30000, 30000, True)
        self.wait(ms / 1000 + 2)
        known = {l.addr for l in self.lights}
        for addr in sorted(self.found):  # sorted by MAC so numbering is stable
            if addr not in known:
                at, name = self.found[addr]
                self.lights.append(Light(self, at, addr, name))
        self.lights.sort(key=lambda l: l.addr)
        for l in self.lights:
            l.connect()
        return self.lights
