"""Phase 2: telemetry ingest persists to DB and is served via the REST API."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.ingest import ingest_telemetry
from backend.main import app, get_session
from backend.models import Base


def _memory_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _record(vin="VIN-001"):
    return {
        "vin": vin,
        "ts": datetime.now(timezone.utc).isoformat(),
        "signals": {"VehicleSpeed": 60.0, "CoolantTemp": 90.0, "StateOfCharge": 77.0},
        "fw_version": "1.2.0",
    }


def test_ingest_and_query():
    Session = _memory_session_factory()
    with Session() as s:
        ingest_telemetry(s, _record())
        ingest_telemetry(s, _record())  # second cycle

    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[get_session] = override
    client = TestClient(app)

    vehicles = client.get("/vehicles").json()
    assert len(vehicles) == 1
    assert vehicles[0]["vin"] == "VIN-001"
    assert vehicles[0]["fw_version"] == "1.2.0"

    telem = client.get("/vehicles/VIN-001/telemetry").json()
    # 3 signals x 2 cycles = 6 readings
    assert len(telem) == 6
    assert client.get("/vehicles/NOPE/telemetry").status_code == 404
    app.dependency_overrides.clear()
