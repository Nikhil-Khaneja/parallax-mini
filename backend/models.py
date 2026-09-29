"""SQLAlchemy models: vehicles, signal_readings, firmware, campaigns."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (Column, DateTime, Float, ForeignKey, Integer, String,
                        Text)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Vehicle(Base):
    __tablename__ = "vehicles"
    vin = Column(String, primary_key=True)
    fw_version = Column(String, default="1.0.0")
    last_seen = Column(DateTime)
    health_score = Column(Float, default=0.0)  # 0 healthy .. 1 anomalous


class SignalReading(Base):
    __tablename__ = "signal_readings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String, ForeignKey("vehicles.vin"), index=True)
    ts = Column(DateTime, index=True)
    signal = Column(String, index=True)
    value = Column(Float)


class Firmware(Base):
    __tablename__ = "firmware"
    version = Column(String, primary_key=True)
    sha256 = Column(String, nullable=False)
    sig = Column(Text, nullable=False)  # base64 Ed25519 signature


class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(String, primary_key=True)
    fw_version = Column(String, ForeignKey("firmware.version"))
    target_pct = Column(Integer, default=100)
    canary_pct = Column(Integer, default=20)
    state = Column(String, default="created")
    created_at = Column(DateTime, default=datetime.utcnow)
    vehicles = relationship("CampaignVehicle", cascade="all, delete-orphan")


class CampaignVehicle(Base):
    __tablename__ = "campaign_vehicles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), index=True)
    vin = Column(String, ForeignKey("vehicles.vin"))
    status = Column(String, default="pending")  # pending|applied|rolled_back
    reason = Column(String, default="")
    prev_fw = Column(String, default="")
