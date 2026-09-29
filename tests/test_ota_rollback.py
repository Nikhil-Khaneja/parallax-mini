"""Phase 4: OTA campaign applies valid firmware and rolls back on failure."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.crypto import generate_keypair, sha256_hex, sign
from backend.models import Base, Firmware, Vehicle
from backend.ota import launch_campaign
from simulator.ota_agent import OtaAgent

_PRIV, _PUB = generate_keypair()


def _setup(n=5):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    s = Session()
    for i in range(n):
        s.add(Vehicle(vin=f"VIN-{i:03d}", fw_version="1.0.0", health_score=0.0))
    s.commit()
    agents = {f"VIN-{i:03d}": OtaAgent(_PUB, "1.0.0") for i in range(n)}
    return s, agents


def _register_fw(session, artifact, version, sign_over=None):
    checksum = sha256_hex(artifact)
    sig = sign(_PRIV, sign_over if sign_over else checksum)
    session.add(Firmware(version=version, sha256=checksum, sig=sig))
    session.commit()


def test_valid_campaign_succeeds():
    s, agents = _setup(5)
    artifact = b"firmware-1.5.0-good"
    _register_fw(s, artifact, "1.5.0")

    c = launch_campaign(s, "1.5.0", artifact, agents, target_pct=100, canary_pct=20)

    assert c.state == "succeeded"
    assert all(a.fw_version == "1.5.0" for a in agents.values())
    assert all(cv.status == "applied" for cv in c.vehicles)


def test_checksum_mismatch_rolls_back():
    s, agents = _setup(5)
    artifact = b"firmware-1.5.0-good"
    _register_fw(s, artifact, "1.5.0")

    # Corrupt the artifact AFTER registration so its sha256 no longer matches.
    corrupted = b"firmware-1.5.0-TAMPERED"
    c = launch_campaign(s, "1.5.0", corrupted, agents, target_pct=100, canary_pct=20)

    assert c.state == "rolled_back"
    # Every vehicle remains on the previous firmware.
    assert all(a.fw_version == "1.0.0" for a in agents.values())
    for v in s.query(Vehicle).all():
        assert v.fw_version == "1.0.0"
    # At least one vehicle recorded the checksum failure reason.
    reasons = {cv.reason for cv in c.vehicles}
    assert "checksum_mismatch" in reasons


def test_bad_signature_rolls_back():
    s, agents = _setup(5)
    artifact = b"firmware-2.0.0"
    # Sign over the WRONG checksum -> signature verification must fail.
    _register_fw(s, artifact, "2.0.0", sign_over="deadbeef")

    c = launch_campaign(s, "2.0.0", artifact, agents, target_pct=100, canary_pct=20)

    assert c.state == "rolled_back"
    assert all(a.fw_version == "1.0.0" for a in agents.values())
    assert "bad_signature" in {cv.reason for cv in c.vehicles}
