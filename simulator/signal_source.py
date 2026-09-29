"""Signal sources: produce {signal_name: value} at a given time.

SyntheticSource generates physically plausible, correlated signals:
speed drives RPM and coolant temp; state-of-charge drains with speed.
A `fault` flag injects a runaway coolant-temp anomaly (for the ML gate demo).
"""
from __future__ import annotations

import math
import random
from typing import Dict

# San Jose-ish origin for GPS drift
_LAT0, _LON0 = 37.3382, -121.8863


class SyntheticSource:
    def __init__(self, seed: int = 0, fault: bool = False) -> None:
        self._rng = random.Random(seed)
        self._soc = 80.0 + self._rng.uniform(-5, 5)
        self._fault = fault

    def sample(self, t: float) -> Dict[str, float]:
        # Speed: smooth oscillation 0..~90 km/h with noise
        speed = max(0.0, 45 + 40 * math.sin(t / 30.0) + self._rng.uniform(-3, 3))
        rpm = 800 + speed * 35 + self._rng.uniform(-50, 50)
        # SoC drains slowly with speed
        self._soc = max(0.0, self._soc - speed * 5e-5)
        # Coolant temp rises with load; fault makes it run away
        base_temp = 80 + speed * 0.15
        temp = base_temp + (t * 1.5 if self._fault else self._rng.uniform(-1, 1))
        temp = min(214.0, temp)
        # GPS drifts a little from origin
        lat = _LAT0 + 0.0005 * math.sin(t / 50.0)
        lon = _LON0 + 0.0005 * math.cos(t / 50.0)
        return {
            "VehicleSpeed": round(speed, 2),
            "EngineRPM": round(rpm),
            "StateOfCharge": round(self._soc, 1),
            "CoolantTemp": round(temp, 1),
            "GPS_Lat": round(lat, 6),
            "GPS_Lon": round(lon, 6),
        }
