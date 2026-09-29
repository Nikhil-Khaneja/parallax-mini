"""FastAPI app: fleet observability REST API."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select

from .db import SessionLocal, init_db
from .models import Campaign, SignalReading, Vehicle


@asynccontextmanager
async def lifespan(_app: FastAPI):  # pragma: no cover
    init_db()
    yield


app = FastAPI(title="Parallax Mini", lifespan=lifespan)


def get_session():
    with SessionLocal() as session:
        yield session


@app.get("/vehicles")
def list_vehicles(session=Depends(get_session)):
    rows = session.execute(select(Vehicle)).scalars().all()
    return [
        {"vin": v.vin, "fw_version": v.fw_version,
         "last_seen": v.last_seen.isoformat() if v.last_seen else None,
         "health_score": v.health_score}
        for v in rows
    ]


@app.get("/vehicles/{vin}/telemetry")
def vehicle_telemetry(vin: str, limit: int = 50, session=Depends(get_session)):
    if session.get(Vehicle, vin) is None:
        raise HTTPException(404, "unknown vin")
    stmt = (select(SignalReading).where(SignalReading.vin == vin)
            .order_by(SignalReading.id.desc()).limit(limit))
    rows = session.execute(stmt).scalars().all()
    return [
        {"ts": r.ts.isoformat(), "signal": r.signal, "value": r.value}
        for r in rows
    ]


def _campaign_json(c: Campaign):
    return {
        "campaign_id": c.id, "fw_version": c.fw_version, "state": c.state,
        "target_pct": c.target_pct, "canary_pct": c.canary_pct,
        "vehicles": [
            {"vin": cv.vin, "status": cv.status, "reason": cv.reason,
             "prev_fw": cv.prev_fw}
            for cv in c.vehicles
        ],
    }


@app.get("/ota/campaigns")
def list_campaigns(session=Depends(get_session)):
    rows = session.execute(select(Campaign).order_by(Campaign.created_at.desc())).scalars().all()
    return [_campaign_json(c) for c in rows]


@app.get("/ota/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, session=Depends(get_session)):
    c = session.get(Campaign, campaign_id)
    if c is None:
        raise HTTPException(404, "unknown campaign")
    return _campaign_json(c)
