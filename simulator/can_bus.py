"""CAN bus abstraction.

Two transports with identical semantics:
- VirtualBus: in-process queue, works anywhere (used for tests and non-Linux dev).
- SocketCanBus: real Linux SocketCAN `vcan` via python-can (default on Linux).

A frame is just (arbitration_id: int, data: bytes).
"""
from __future__ import annotations

import queue
from typing import Optional, Tuple

Frame = Tuple[int, bytes]


class VirtualBus:
    """In-process CAN bus backed by a thread-safe queue."""

    def __init__(self) -> None:
        self._q: "queue.Queue[Frame]" = queue.Queue()

    def send(self, arb_id: int, data: bytes) -> None:
        self._q.put((arb_id, data))

    def recv(self, timeout: Optional[float] = None) -> Optional[Frame]:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:  # symmetry with SocketCanBus
        pass


class SocketCanBus:
    """Real SocketCAN transport. Requires python-can and a `vcan` interface."""

    def __init__(self, channel: str = "vcan0") -> None:
        import can  # lazy import: only needed on Linux with python-can

        self._bus = can.interface.Bus(channel=channel, interface="socketcan")

    def send(self, arb_id: int, data: bytes) -> None:
        import can

        self._bus.send(can.Message(arbitration_id=arb_id, data=data, is_extended_id=False))

    def recv(self, timeout: Optional[float] = None) -> Optional[Frame]:
        msg = self._bus.recv(timeout=timeout)
        if msg is None:
            return None
        return (msg.arbitration_id, bytes(msg.data))

    def close(self) -> None:
        self._bus.shutdown()
