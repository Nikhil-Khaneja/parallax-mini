"""Telemetry ingestion.

`ingest_telemetry` is a pure DB function (easy to test). `run_subscriber`
wires it to MQTT for the live system.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict

from .models import SignalReading, Vehicle


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)


def ingest_telemetry(session, record: Dict, detector=None) -> None:
    """Upsert the vehicle and append its signal readings.

    If a detector is provided, update the vehicle's health_score from the
    latest signals (used to gate OTA eligibility).
    """
    vin = record["vin"]
    ts = _parse_ts(record["ts"])
    vehicle = session.get(Vehicle, vin)
    if vehicle is None:
        vehicle = Vehicle(vin=vin)
        session.add(vehicle)
    vehicle.fw_version = record.get("fw_version", vehicle.fw_version)
    vehicle.last_seen = ts
    for name, value in record["signals"].items():
        session.add(SignalReading(vin=vin, ts=ts, signal=name, value=float(value)))
    if detector is not None:
        vehicle.health_score = detector.update(vin, record["signals"])
    session.commit()


def run_subscriber(session_factory, host: str = None) -> None:  # pragma: no cover
    """Subscribe to fleet/+/telemetry and ingest each message."""
    import paho.mqtt.client as mqtt

    from ml.detector import AnomalyDetector

    host = host or os.environ.get("MQTT_HOST", "localhost")
    detector = AnomalyDetector()

    def on_message(_c, _u, msg):
        with session_factory() as session:
            ingest_telemetry(session, json.loads(msg.payload), detector=detector)

    client = mqtt.Client()
    client.on_message = on_message
    client.connect(host, 1883)
    client.subscribe("fleet/+/telemetry")
    client.loop_forever()
