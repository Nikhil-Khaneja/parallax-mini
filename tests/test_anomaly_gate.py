"""Phase 5: the anomaly detector flags a faulty vehicle and the OTA engine
holds it back from a campaign."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.crypto import generate_keypair, sha256_hex, sign
from backend.ingest import ingest_telemetry
from backend.models import Base, Firmware, Vehicle
from backend.ota import launch_campaign
from ml.detector import AnomalyDetector
from simulator.fleet import Vehicle as SimVehicle
from simulator.ota_agent import OtaAgent

_PRIV, _PUB = generate_keypair()


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_detector_scores_fault_high():
    det = AnomalyDetector()
    healthy = SimVehicle("VIN-000", seed=0, fault=False)
    faulty = SimVehicle("VIN-001", seed=1, fault=True)
    hs = fs = 0.0
    for t in range(30):
        hs = det.update("VIN-000", healthy.tick(float(t))["signals"])
        fs = det.update("VIN-001", faulty.tick(float(t))["signals"])
    assert fs > 0.8          # runaway coolant temp -> anomalous
    assert hs < 0.5          # healthy stays low
    assert fs > hs


def test_faulty_vehicle_excluded_from_campaign():
    s = _session()
    det = AnomalyDetector()
    sims = {f"VIN-{i:03d}": SimVehicle(f"VIN-{i:03d}", seed=i, fault=(i == 2))
            for i in range(5)}
    agents = {vin: OtaAgent(_PUB, "1.0.0") for vin in sims}

    for t in range(30):
        for vin, sim in sims.items():
            ingest_telemetry(s, sim.tick(float(t)), detector=det)

    # The faulty vehicle (VIN-002) should have a high health score.
    assert s.get(Vehicle, "VIN-002").health_score > 0.8

    artifact = b"firmware-1.5.0"
    s.add(Firmware(version="1.5.0", sha256=sha256_hex(artifact),
                   sig=sign(_PRIV, sha256_hex(artifact))))
    s.commit()

    c = launch_campaign(s, "1.5.0", artifact, agents, target_pct=100, canary_pct=20)

    assert c.state == "succeeded"
    # Healthy vehicles updated; the faulty one was held back.
    assert agents["VIN-002"].fw_version == "1.0.0"
    assert s.get(Vehicle, "VIN-002").fw_version == "1.0.0"
    updated = [vin for vin, a in agents.items() if a.fw_version == "1.5.0"]
    assert "VIN-002" not in updated
    assert len(updated) == 4
