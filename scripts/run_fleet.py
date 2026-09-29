#!/usr/bin/env python
"""Run a fleet and publish telemetry to MQTT: fleet/<vin>/telemetry.

Config via env: FLEET_SIZE (20), SAMPLE_HZ (1), MQTT_HOST (localhost),
FAULT_VIN (optional index to inject a fault, e.g. 2).
"""
import json
import os
import sys
import time

sys.path.insert(0, ".")
from simulator.fleet import Vehicle  # noqa: E402


def main() -> None:
    import paho.mqtt.client as mqtt

    size = int(os.environ.get("FLEET_SIZE", "20"))
    hz = float(os.environ.get("SAMPLE_HZ", "1"))
    host = os.environ.get("MQTT_HOST", "localhost")
    fault_vin = os.environ.get("FAULT_VIN")
    fault_idx = int(fault_vin) if fault_vin is not None else -1

    fleet = [Vehicle(f"VIN-{i:03d}", seed=i, fault=(i == fault_idx)) for i in range(size)]
    client = mqtt.Client()
    client.connect(host, 1883)
    client.loop_start()

    t, period = 0.0, 1.0 / hz
    while True:
        for v in fleet:
            rec = v.tick(t)
            if rec:
                client.publish(f"fleet/{v.vin}/telemetry", json.dumps(rec))
        time.sleep(period)
        t += period


if __name__ == "__main__":
    main()
