"""gateway_agent: read CAN frames, DBC-decode, assemble telemetry JSON.

Powertrain + Position frames are merged into one telemetry record per cycle.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from .codec import Codec

_FRAMES_PER_CYCLE = 2  # Powertrain + Position


def read_telemetry(bus, codec: Codec, vin: str, fw_version: str,
                   timeout: float = 1.0) -> Optional[Dict]:
    """Read one full cycle of frames and return a telemetry record, or None."""
    signals: Dict[str, float] = {}
    for _ in range(_FRAMES_PER_CYCLE):
        frame = bus.recv(timeout=timeout)
        if frame is None:
            break
        signals.update(codec.decode(frame[0], frame[1]))
    if not signals:
        return None
    return {
        "vin": vin,
        "ts": datetime.now(timezone.utc).isoformat(),
        "signals": signals,
        "fw_version": fw_version,
    }
