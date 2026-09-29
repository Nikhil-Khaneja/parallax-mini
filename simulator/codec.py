"""DBC codec: map a flat signal dict to/from CAN frames using fleet.dbc."""
from __future__ import annotations

import os
from typing import Dict, Iterator, Tuple

import cantools

_DBC_PATH = os.path.join(os.path.dirname(__file__), "..", "dbc", "fleet.dbc")
_MESSAGES = ("Powertrain", "Position")


class Codec:
    def __init__(self, dbc_path: str = _DBC_PATH) -> None:
        self._db = cantools.database.load_file(dbc_path)

    def encode(self, signals: Dict[str, float]) -> Iterator[Tuple[int, bytes]]:
        """Yield (arbitration_id, data) frames for the given signals."""
        for name in _MESSAGES:
            msg = self._db.get_message_by_name(name)
            subset = {s.name: signals[s.name] for s in msg.signals}
            yield msg.frame_id, msg.encode(subset)

    def decode(self, arb_id: int, data: bytes) -> Dict[str, float]:
        return self._db.decode_message(arb_id, data)
