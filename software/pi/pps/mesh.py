"""Off-grid neighborhood messaging through a Meshtastic LoRa node on the Pi's USB port.

The node keeps relaying other people's messages even while the Pi is asleep; the Pi just
reads and shows them (and can send short ones) when it's awake.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class Message:
    when: float
    sender: str
    text: str
    mine: bool = False


@dataclass
class Node:
    name: str
    short: str
    lat: float | None
    lon: float | None
    last_heard: float | None


class Mesh:
    def __init__(self, port: str = "", keep: int = 50):
        self.messages: deque[Message] = deque(maxlen=keep)
        self.iface = None
        self.port = port
        self.error = ""

    def start(self) -> None:
        try:
            import meshtastic.serial_interface
            from pubsub import pub
        except ImportError:
            self.error = "meshtastic not installed"
            return
        try:
            self.iface = meshtastic.serial_interface.SerialInterface(self.port or None)
        except Exception as e:  # no node plugged in, permissions, ...
            self.error = f"no mesh node ({e.__class__.__name__})"
            log.warning("mesh: %s", e)
            return
        pub.subscribe(self._on_text, "meshtastic.receive.text")

    def _name_for(self, node_id) -> str:
        try:
            info = self.iface.nodes.get(node_id) or {}
            return info.get("user", {}).get("shortName") or str(node_id)
        except Exception:
            return str(node_id)

    def _on_text(self, packet, interface=None):
        text = packet.get("decoded", {}).get("text", "")
        if text:
            self.messages.append(Message(time.time(), self._name_for(packet.get("fromId")), text))

    @property
    def online(self) -> bool:
        return self.iface is not None

    def send(self, text: str) -> bool:
        if not self.iface:
            return False
        try:
            self.iface.sendText(text[:200])
            self.messages.append(Message(time.time(), "me", text, mine=True))
            return True
        except Exception as e:
            log.warning("mesh send failed: %s", e)
            return False

    def nodes(self) -> list[Node]:
        if not self.iface:
            return []
        out = []
        for info in (self.iface.nodes or {}).values():
            user = info.get("user", {})
            pos = info.get("position", {})
            out.append(Node(user.get("longName", "?"), user.get("shortName", "?"),
                            pos.get("latitude"), pos.get("longitude"), info.get("lastHeard")))
        return out

    def my_position(self) -> tuple[float, float] | None:
        try:
            pos = self.iface.getMyNodeInfo().get("position", {})
            if "latitude" in pos:
                return pos["latitude"], pos["longitude"]
        except Exception:
            pass
        return None

    def close(self) -> None:
        if self.iface:
            try:
                self.iface.close()
            except Exception:
                pass


class FakeMesh(Mesh):
    """Used by the simulator: a few neighbors and messages."""

    def __init__(self, messages=(), nodes=(), me=None):
        super().__init__()
        for m in messages:
            self.messages.append(m)
        self._nodes = list(nodes)
        self._me = me

    def start(self):
        pass

    @property
    def online(self):
        return True

    def send(self, text):
        self.messages.append(Message(time.time(), "me", text, mine=True))
        return True

    def nodes(self):
        return self._nodes

    def my_position(self):
        return self._me
