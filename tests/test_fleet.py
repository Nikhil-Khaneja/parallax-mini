"""Phase 3: a fleet of N logical vehicles each emit distinct telemetry."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.ingest import ingest_telemetry
from backend.models import Base, Vehicle
from simulator.fleet import make_fleet


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def test_fleet_of_20_ingests_distinctly():
    fleet = make_fleet(20)
    Session = _session()
    with Session() as s:
        for t in range(3):  # 3 cycles
            for v in fleet:
                rec = v.tick(float(t))
                assert rec is not None
                ingest_telemetry(s, rec)
        vins = s.execute(select(Vehicle.vin)).scalars().all()

    assert len(vins) == 20
    assert len(set(vins)) == 20


def test_vehicles_have_different_states():
    fleet = make_fleet(5)
    speeds = {v.vin: v.tick(12.0)["signals"]["VehicleSpeed"] for v in fleet}
    # Different seeds -> not all identical
    assert len(set(speeds.values())) > 1
