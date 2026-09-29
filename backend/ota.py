"""OTA campaign engine: staged canary rollout with automatic rollback.

The engine drives a campaign over a set of vehicle agents (vin -> OtaAgent):
  created -> canary -> rollout -> succeeded
                    \\-> rolled_back (on any canary/rollout failure)

Only vehicles with health_score <= threshold are eligible (anomaly gate).
Each vehicle verifies signature + checksum locally; a failure rolls the
affected vehicles back to their previous firmware and halts the campaign.
"""
from __future__ import annotations

import math
import os
import uuid
from typing import Dict, List

from .models import Campaign, CampaignVehicle, Firmware, Vehicle

ANOMALY_THRESHOLD = float(os.environ.get("ANOMALY_THRESHOLD", "0.8"))


def _eligible_vins(session, threshold: float) -> List[str]:
    vins = []
    for v in session.query(Vehicle).order_by(Vehicle.vin).all():
        if (v.health_score or 0.0) <= threshold:
            vins.append(v.vin)
    return vins


def _push(session, campaign, vins, artifact, fw, agents) -> bool:
    """Push firmware to each vin; return True if all applied, else roll back."""
    applied: List[CampaignVehicle] = []
    for vin in vins:
        agent = agents[vin]
        prev = agent.fw_version
        cv = CampaignVehicle(campaign_id=campaign.id, vin=vin, prev_fw=prev)
        ok, reason = agent.apply_update(artifact, fw.version, fw.sha256, fw.sig)
        cv.status = "applied" if ok else "rolled_back"
        cv.reason = reason
        session.add(cv)
        if ok:
            session.get(Vehicle, vin).fw_version = fw.version
            applied.append(cv)
        else:
            # roll back everything applied so far in this stage
            for done in applied:
                agents[done.vin].fw_version = done.prev_fw
                session.get(Vehicle, done.vin).fw_version = done.prev_fw
                done.status = "rolled_back"
                done.reason = "canary_failed"
            session.commit()
            return False
    session.commit()
    return True


def launch_campaign(session, fw_version: str, artifact: bytes,
                    agents: Dict[str, object], target_pct: int = 100,
                    canary_pct: int = 20, threshold: float = ANOMALY_THRESHOLD) -> Campaign:
    fw = session.get(Firmware, fw_version)
    if fw is None:
        raise ValueError("unknown firmware version")

    campaign = Campaign(id=f"c-{uuid.uuid4().hex[:8]}", fw_version=fw_version,
                        target_pct=target_pct, canary_pct=canary_pct, state="created")
    session.add(campaign)
    session.commit()

    eligible = _eligible_vins(session, threshold)
    n_target = max(1, math.floor(len(eligible) * target_pct / 100)) if eligible else 0
    targets = eligible[:n_target]
    if not targets:
        campaign.state = "succeeded"
        session.commit()
        return campaign

    n_canary = max(1, math.floor(len(targets) * canary_pct / 100))
    canary, rest = targets[:n_canary], targets[n_canary:]

    campaign.state = "canary"
    session.commit()
    if not _push(session, campaign, canary, artifact, fw, agents):
        campaign.state = "rolled_back"
        session.commit()
        return campaign

    campaign.state = "rollout"
    session.commit()
    if rest and not _push(session, campaign, rest, artifact, fw, agents):
        campaign.state = "rolled_back"
        session.commit()
        return campaign

    campaign.state = "succeeded"
    session.commit()
    return campaign
