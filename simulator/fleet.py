"""Fleet: run N logical vehicles concurrently.

Each vehicle owns a VirtualBus, generates a sample, and its gateway decodes
one telemetry record per tick. A `sink` callable receives each record
(e.g., publish to MQTT, or collect in tests).
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Dict, List

from .can_bus import VirtualBus
from .can_generator import generate_once
from .codec import Codec
from .gateway_agent import read_telemetry
from .signal_source import SyntheticSource

Sink = Callable[[Dict], None]


class Vehicle:
    def __init__(self, vin: str, fw_version: str = "1.0.0",
                 seed: int = 0, fault: bool = False) -> None:
        self.vin = vin
        self.fw_version = fw_version
        self._bus = VirtualBus()
        self._codec = Codec()
        self._source = SyntheticSource(seed=seed, fault=fault)

    def tick(self, t: float) -> Dict:
        """Produce one telemetry record for time `t`."""
        generate_once(self._bus, self._codec, self._source, t)
        return read_telemetry(self._bus, self._codec, self.vin, self.fw_version, timeout=0.1)


def make_fleet(size: int, fw_version: str = "1.0.0") -> List[Vehicle]:
    return [Vehicle(f"VIN-{i:03d}", fw_version=fw_version, seed=i) for i in range(size)]


async def run_fleet(vehicles: List[Vehicle], sink: Sink,
                    hz: float = 1.0, ticks: int = None) -> None:  # pragma: no cover
    """Drive the fleet at `hz`; run `ticks` cycles or forever if None."""
    period = 1.0 / hz
    t = 0.0
    n = 0
    while ticks is None or n < ticks:
        for v in vehicles:
            rec = v.tick(t)
            if rec:
                sink(rec)
        await asyncio.sleep(period)
        t += period
        n += 1
