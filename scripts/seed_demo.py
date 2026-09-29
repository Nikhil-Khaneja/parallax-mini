#!/usr/bin/env python
"""Seed the DB with a demo fleet + one OTA campaign (for demo/smoke test)."""
import sys

sys.path.insert(0, ".")
from datetime import datetime

from backend.crypto import generate_keypair, sha256_hex, sign  # noqa: E402
from backend.db import SessionLocal, init_db  # noqa: E402
from backend.models import Firmware, Vehicle  # noqa: E402
from backend.ota import launch_campaign  # noqa: E402
from simulator.ota_agent import OtaAgent  # noqa: E402


def main() -> None:
    init_db()
    priv, pub = generate_keypair()
    with SessionLocal() as s:
        for i in range(5):
            s.merge(Vehicle(vin=f"VIN-{i:03d}", fw_version="1.0.0",
                            last_seen=datetime.utcnow(),
                            health_score=1.0 if i == 2 else 0.1))
        artifact = b"firmware-1.5.0"
        s.merge(Firmware(version="1.5.0", sha256=sha256_hex(artifact),
                         sig=sign(priv, sha256_hex(artifact))))
        s.commit()
        agents = {f"VIN-{i:03d}": OtaAgent(pub, "1.0.0") for i in range(5)}
        c = launch_campaign(s, "1.5.0", artifact, agents, target_pct=100, canary_pct=20)
        print("seeded; campaign", c.id, c.state)


if __name__ == "__main__":
    main()
