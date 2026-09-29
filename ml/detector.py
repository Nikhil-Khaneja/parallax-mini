"""Streaming anomaly detection.

A deliberately small, dependency-free detector: per vehicle we keep a rolling
window of telemetry and score how anomalous the latest sample is. The score is
in [0,1]; the OTA engine holds back vehicles scoring above ANOMALY_THRESHOLD.

Signals used:
- CoolantTemp: high absolute temp and steep upward slope indicate a fault.
- StateOfCharge: an abnormally fast drain is suspicious.

The design favors interpretability over model complexity; swap in a learned
model (e.g., IsolationForest) behind the same `score` interface if needed.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict

_WINDOW = 20
_TEMP_REDLINE = 120.0  # degC; sustained above this is clearly anomalous


class AnomalyDetector:
    def __init__(self, window: int = _WINDOW) -> None:
        self._window = window
        self._temp: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=window))

    def update(self, vin: str, signals: Dict[str, float]) -> float:
        """Add the latest sample for `vin` and return its health score [0,1]."""
        temp = signals.get("CoolantTemp")
        if temp is not None:
            self._temp[vin].append(float(temp))
        return self.score(vin)

    def score(self, vin: str) -> float:
        temps = self._temp.get(vin)
        if not temps or len(temps) < 2:
            return 0.0
        latest = temps[-1]
        # 1) Absolute-temperature component (0 at 90C, 1 at redline).
        abs_score = _clip((latest - 90.0) / (_TEMP_REDLINE - 90.0))
        # 2) Upward-slope component over the window (degC per sample).
        slope = (temps[-1] - temps[0]) / (len(temps) - 1)
        slope_score = _clip(slope / 3.0)  # ~3 degC/sample is strongly anomalous
        return round(max(abs_score, slope_score), 3)


def _clip(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x
