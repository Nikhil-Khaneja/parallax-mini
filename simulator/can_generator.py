"""can_generator: sample a signal source and write DBC-encoded frames to the bus."""
from __future__ import annotations

from .codec import Codec


def generate_once(bus, codec: Codec, source, t: float) -> None:
    """Encode one sample from `source` at time `t` and send its frames."""
    signals = source.sample(t)
    for arb_id, data in codec.encode(signals):
        bus.send(arb_id, data)
