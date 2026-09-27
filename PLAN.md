# PLAN.md — Parallax Mini

Specific, phased build plan. Each phase is independently demoable. Code principle: **smallest correct solution, no speculative abstraction, no dead code.**

## Locked scope

| Decision | Choice |
|---|---|
| OTA integrity | Ed25519 signature + SHA-256 checksum |
| OTA rollout | Staged canary (default 20%) → full, with automatic rollback |
| Fleet size | 20 vehicles (containers). Async "logical vehicles" mode for larger honest claims. |
| Signal source | Pluggable: `synthetic` (default) or `replay` (Vehicle Energy Dataset) |
| Transport | CAN over SocketCAN `vcan` → decode → MQTT |
| Backend | FastAPI + PostgreSQL (SQLAlchemy) |
| Frontend | React (Vite) |
| ML | Streaming anomaly detection gating OTA eligibility |
| Out of scope (for now) | mTLS on MQTT, multi-cloud deploy, real ECU flashing |

## Tech stack

- **Simulator:** Python, `python-can`, `cantools`, `paho-mqtt`
- **Broker:** Eclipse Mosquitto
- **Backend:** FastAPI, SQLAlchemy, `paho-mqtt`, `cryptography` (Ed25519), PostgreSQL
- **ML:** scikit-learn (River optional for true streaming); numpy
- **Frontend:** React + Vite, a charting lib, a map lib
- **Infra:** Docker Compose, pytest

## Data model (PostgreSQL)

```
vehicles(vin PK, fw_version, last_seen, health_score)
signal_readings(id PK, vin FK, ts, signal, value)      -- time-series telemetry
firmware(version PK, sha256, sig, blob_ref)            -- registered artifacts
campaigns(id PK, fw_version FK, target_pct, canary_pct, state, created_at)
campaign_vehicles(campaign_id FK, vin FK, status, reason, prev_fw)  -- per-vehicle rollout state
```

## Signal source interface (pluggable)

```python
class SignalSource(Protocol):
    def sample(self, t: float) -> dict[str, float]: ...   # {signal_name: value}
```
- `SyntheticSource`: physically plausible speed/SoC/temp/GPS with correlations (speed↑ → temp↑, SoC↓).
- `ReplaySource`: reads a VED trip CSV, yields real speed/GPS/SoC over time. Raw data is **not committed**; a loader script downloads it.

## DBC signals (`dbc/fleet.dbc`)

`VehicleSpeed` (km/h), `EngineRPM`, `StateOfCharge` (%), `CoolantTemp` (°C), `GPS_Lat`, `GPS_Lon`. Minimal but realistic; enough for decode round-trip and a map.

## MQTT topics

| Topic | Direction | Payload |
|---|---|---|
| `fleet/<vin>/telemetry` | vehicle → cloud | `{vin, ts, signals{}, fw_version}` |
| `fleet/<vin>/ota/cmd` | cloud → vehicle | `{campaign_id, version, sha256, sig, blob_ref}` |
| `fleet/<vin>/ota/status` | vehicle → cloud | `{vin, campaign_id, status, reason, active_fw}` |

## REST API (FastAPI)

| Method | Path | Purpose |
|---|---|---|
| GET | `/vehicles` | Fleet list + fw + health |
| GET | `/vehicles/{vin}/telemetry?since=` | Recent signal series |
| POST | `/firmware` | Register signed artifact `{version, sha256, sig}` |
| POST | `/ota/campaigns` | Launch `{version, target_pct}` |
| GET | `/ota/campaigns/{id}` | Campaign + per-vehicle status |
| WS | `/ws/telemetry` | Live push to dashboard |

## Phases

### Phase 1 — CAN core (simulator)
- `dbc/fleet.dbc`; `simulator/signal_source.py` (synthetic); `simulator/can_generator.py` (DBC-encode → `vcan`); `simulator/gateway_agent.py` (read → `cantools` decode → JSON).
- **Done when:** encode→decode round-trip test passes for all signals.

### Phase 2 — MQTT + ingest
- Mosquitto in compose; gateway publishes telemetry; `backend/ingest.py` subscribes → Postgres; `backend/models.py`; REST `GET /vehicles`, `/telemetry`.
- **Done when:** a published sample appears via REST.

### Phase 3 — Fleet scale
- Parameterize simulator by `VIN`; compose scales to `FLEET_SIZE=20`. Optional async logical-vehicle mode in one container.
- **Done when:** 20 vehicles stream concurrently; dashboard-less REST confirms all present.

### Phase 4 — OTA engine (centerpiece)
- `scripts/gen_keys.py` (Ed25519 keypair); `scripts/sign_firmware.py` (sha256 + sign).
- `backend/ota.py` state machine (Created→Canary→Verifying→Rollout→Succeeded / RolledBack); `simulator/ota_agent.py` verifies sig+checksum, applies, reports, rolls back.
- **Done when:** `tests/test_ota_rollback.py` forces a checksum mismatch and asserts affected vehicles revert to `prev_fw` and campaign halts.

### Phase 5 — ML anomaly gate
- `ml/features.py` (rolling window features per vehicle: mean/var/slope of temp, SoC drop rate, speed variance).
- `ml/detector.py`: unsupervised anomaly model (IsolationForest or streaming half-space trees) → per-vehicle `health_score` in `[0,1]`.
- Wire into `ingest.py` (score on each batch) and `ota.py` (exclude vehicles with `score > ANOMALY_THRESHOLD`).
- Synthetic fault injection in `SyntheticSource` (e.g., runaway CoolantTemp) to produce anomalies for the demo/tests.
- **Done when:** `tests/test_anomaly_gate.py` shows an injected-fault vehicle is excluded from a campaign's target set.

### Phase 6 — React dashboard
- Live signal table + gauges (WS), GPS fleet map, anomaly-score column, OTA campaign launcher with live per-vehicle rollout/rollback progress.
- **Done when:** end-to-end demo: launch campaign, watch canary → rollout, observe a forced rollback in UI.

### Phase 7 — Polish
- One-command `docker compose up`; seed script; README diagrams verified; `pytest` green in CI (GitHub Actions).

## I/O contract (canonical example)

Telemetry:
```json
{"vin":"VIN-007","ts":"2026-09-27T10:22:03.412Z",
 "signals":{"VehicleSpeed":62.5,"StateOfCharge":78.3,"CoolantTemp":91.0,
            "GPS_Lat":37.3382,"GPS_Lon":-121.8863},
 "fw_version":"1.4.2"}
```
Campaign result:
```json
{"campaign_id":"c-2231","state":"rolled_back","target_pct":20,
 "vehicles":[{"vin":"VIN-003","status":"applied","fw_version":"1.5.0"},
             {"vin":"VIN-007","status":"rolled_back","reason":"checksum_mismatch","prev_fw":"1.4.2"}]}
```

## Portability (SocketCAN)

`vcan` is a Linux kernel module. Design a `CanBus` interface with two implementations:
- `SocketCanBus` (default; real `vcan`, matches the "SocketCAN" claim).
- `VirtualBus` (in-process; used when `vcan` is unavailable on macOS/Windows dev).
Decode logic is identical either way, so the DBC/telemetry path is unchanged.

## Compute

No GPU. ~2–3 GB RAM for the 20-vehicle stack on any modern laptop; 16 GB comfortable for 50+. GPU only relevant if the ML phase is later swapped for a deep model — not required by this plan.

## Honesty guardrails

- Claim "**~20 simulated vehicles**" (or "up to N logical vehicles" only if the async mode is actually run).
- Claim "**SocketCAN `vcan`**" — keep it as the default path; note the portable fallback.
- Claim "**signed OTA with staged rollout and automatic rollback**" — backed by `test_ota_rollback.py`.
- Claim "**streaming anomaly detection gating OTA**" — backed by `test_anomaly_gate.py`.

## Milestone order

1 → 2 → 3 → 4 → 5 → 6 → 7. Phases 4 and 5 are the differentiators; do them rigorously with tests before polishing the UI.
