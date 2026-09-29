"""Phase 1: signals -> CAN frames -> decode round-trips through the bus."""
from simulator.can_bus import VirtualBus
from simulator.can_generator import generate_once
from simulator.codec import Codec
from simulator.gateway_agent import read_telemetry
from simulator.signal_source import SyntheticSource


def test_encode_decode_round_trip():
    bus, codec, src = VirtualBus(), Codec(), SyntheticSource(seed=1)
    original = src.sample(10.0)

    # Re-generate the same sample deterministically and push through the bus.
    src2 = SyntheticSource(seed=1)
    generate_once(bus, codec, src2, 10.0)
    telem = read_telemetry(bus, codec, vin="VIN-001", fw_version="1.0.0", timeout=0.5)

    assert telem is not None
    assert telem["vin"] == "VIN-001"
    for name, value in original.items():
        # DBC quantization tolerance: coarsest scale is CoolantTemp @ 0.5
        assert abs(telem["signals"][name] - value) <= 0.5, name


def test_all_signals_present():
    bus, codec = VirtualBus(), Codec()
    generate_once(bus, codec, SyntheticSource(seed=2), 5.0)
    telem = read_telemetry(bus, codec, vin="VIN-002", fw_version="1.0.0", timeout=0.5)
    assert set(telem["signals"]) == {
        "VehicleSpeed", "EngineRPM", "StateOfCharge",
        "CoolantTemp", "GPS_Lat", "GPS_Lon",
    }
