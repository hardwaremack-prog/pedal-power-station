"""pps-cli - talk to the running Pedal Power Station app from a terminal or SSH.

  pps-cli status                 battery, mode, power in/out (JSON)
  pps-cli set reserve 30         emergency reserve % (10-50)
  pps-cli set speed_cap 12       lower the assist cap (5-15 mph)
  pps-cli set usb 0|1            USB outputs off/on
  pps-cli set out_13v8 0|1       13.8 V output off/on
  pps-cli set dusk_on 0.2        how dark before the lights come on (0-1)
  pps-cli send "Have power to share at Oak & 5th"
  pps-cli tab 2                  show a tab (0 Mesh, 1 Energy, 2 Map, 3 Setup)
  pps-cli time                   copy the Pi's clock to the bike's clock
  pps-cli sleep                  shut the Pi down now
"""

import json
import socket
import sys


def call(msg: dict, port: int = 7341, timeout: float = 3.0) -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    s.sendto(json.dumps(msg).encode(), ("127.0.0.1", port))
    try:
        data, _ = s.recvfrom(65536)
    except socket.timeout:
        return {"ok": False, "error": "no answer - is the pps service running?"}
    return json.loads(data)


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = a[0]
    if cmd == "set" and len(a) == 3:
        msg = {"cmd": "set", "key": a[1], "value": float(a[2])}
    elif cmd == "send" and len(a) >= 2:
        msg = {"cmd": "send", "text": " ".join(a[1:])}
    elif cmd == "tab" and len(a) == 2:
        msg = {"cmd": "tab", "value": int(a[1])}
    elif cmd in ("status", "time", "sleep") and len(a) == 1:
        msg = {"cmd": cmd}
    else:
        print(__doc__)
        return 2
    reply = call(msg)
    print(json.dumps(reply, indent=2))
    return 0 if reply.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
