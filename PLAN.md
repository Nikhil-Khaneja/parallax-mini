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

## Status (2026-09-29)

Phases 1–6 are implemented in Python (commit `1cdaba3`): CAN simulator, MQTT ingest, fleet, signed OTA with rollback, ML anomaly gate, React dashboard, Docker Compose. Phase 7 is partly done: `.github/workflows/` does not exist yet, so CI still needs to be added.

## Next: C++ vehicle side (Phases 8–11)

The Python `simulator/` package stays as the **reference implementation and benchmark baseline**. It is not deleted. A new `vehicle/` directory reimplements the on-vehicle components in C++17. The cloud side (`backend/`, `ml/`) and `dashboard/` stay unchanged.

### Why the vehicle side moves to C++

Not for raw speed: ~20 vehicles × 6 signals at 10–100 Hz is trivial for Python. The reasons:
- **Fidelity.** Real ECU firmware, telematics gateways, and OTA agents run C/C++ on embedded Linux. This project's premise is "real interfaces, not toy abstractions," so the on-vehicle code should be written the way it is in production.
- **SocketCAN is a C API.** The C++ gateway opens a `PF_CAN` raw socket and reads `struct can_frame` directly, the way a real gateway does, instead of going through `python-can`.
- **The OTA agent is safety-critical.** Signature/checksum verification and rollback belong in code with explicit memory and error handling.
- **Measured, not assumed.** Phase 10 benchmarks C++ against the existing Python gateway. Any performance claim must come from those numbers.

### C++ tech stack

CMake (≥3.20, `FetchContent`), Linux SocketCAN (`linux/can.h`), `dbcppp` (DBC encode/decode), `paho.mqtt.cpp`, `nlohmann/json`, `libsodium` (Ed25519 verify + SHA-256), GoogleTest. Build with `-Wall -Wextra -Werror`; run tests under ASan + UBSan in CI. Same `dbc/fleet.dbc`, MQTT topics, and I/O contract as the Python side. No backend changes.

```
vehicle/
  CMakeLists.txt
  include/parallax/   # can_bus.hpp, signal_source.hpp, dbc_codec.hpp, ota_verifier.hpp
  src/                # socketcan_bus.cpp, virtual_bus.cpp, signal_source.cpp, can_generator.cpp, gateway_agent.cpp, ota_agent.cpp
  tests/              # GoogleTest
bench/                # run_bench.py + RESULTS.md
```

### Phase 7 (finish) — CI
- Add `.github/workflows/ci.yml`: install requirements, run `pytest`. (C++ jobs are added in Phase 8.)
- **Done when:** CI is green on `main`.

### Phase 8 — C++ CAN core + gateway
- `CanBus` interface with `SocketCanBus` (raw `PF_CAN` on `vcan0`) and `VirtualBus` (in-process, for macOS dev and tests); `SyntheticSource`; `can_generator` and `gateway_agent` binaries (decode via `dbcppp` → telemetry JSON → MQTT).
- CI job: CMake build + `ctest` under ASan/UBSan.
- **Done when:** GoogleTest round-trip passes for all 6 signals on both buses; a pytest **contract test** decodes C++-generated frames with Python `cantools` and gets identical values (tolerance = signal scale); `docker compose` can run the fleet with the C++ gateway instead of the Python one (`GATEWAY_IMPL=cpp|py`), and existing `test_ingest.py` / `test_fleet.py` still pass.

### Phase 9 — C++ OTA agent
- `ota_agent`: verify Ed25519 signature + SHA-256 with libsodium, apply atomically (write new, then swap), report status on `fleet/<vin>/ota/status`, roll back on failure.
- **Done when:** GoogleTest covers valid / bad-signature / bad-checksum / truncated artifacts; a contract test proves firmware signed by `scripts/sign_firmware.py` (Python `cryptography`) verifies in C++ and a tampered copy fails; existing `test_ota_rollback.py` passes with the C++ agent.

### Phase 10 — Python vs. C++ benchmark
- `bench/run_bench.py` drives both gateways with identical recorded frame streams and reports frames/sec per process, p50/p99 decode-to-publish latency, CPU %, peak RSS, and max vehicles per host before p99 exceeds 50 ms.
- Run on Linux with real `vcan`. Commit `bench/RESULTS.md` with machine spec, commands, and raw numbers (median of 5 runs).
- **Done when:** `RESULTS.md` is reproducible from one command.

### Phase 11 — Docs
- Update README tech stack, architecture diagram, and quick start for the C++ vehicle side, `GATEWAY_IMPL`, and benchmark results (numbers copied from `RESULTS.md` only).

## Honesty guardrails

- Claim "**~20 simulated vehicles**" (or "up to N logical vehicles" only if the async mode is actually run).
- Claim "**SocketCAN `vcan`**" — keep it as the default path; note the portable fallback.
- Claim "**signed OTA with staged rollout and automatic rollback**" — backed by `test_ota_rollback.py`.
- Claim "**streaming anomaly detection gating OTA**" — backed by `test_anomaly_gate.py`.
- Claim "**vehicle-side agents in C++17**" only for components actually implemented in C++ and passing their GoogleTest + contract tests.
- Performance claims ("N× throughput", "p99 X ms") only from `bench/RESULTS.md`, with the machine named. No numbers from memory or estimates.

## Milestone order

1 → 2 → 3 → 4 → 5 → 6 → 7 are built in Python. Next: finish 7 (CI), then 8 → 9 → 10 → 11. Phases 8–10 (C++ gateway, C++ OTA agent, measured benchmark) are the next differentiators; keep the Python `simulator/` working throughout as the baseline.
