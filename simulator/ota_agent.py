"""Vehicle-side OTA agent: verify signature + checksum before applying firmware.

apply_update returns (ok, reason). On any verification failure it refuses to
apply, leaving the vehicle on its previous firmware (caller records rollback).
"""
from __future__ import annotations

from typing import Tuple

from backend.crypto import sha256_hex, verify


class OtaAgent:
    def __init__(self, pub_key, fw_version: str = "1.0.0") -> None:
        self._pub = pub_key
        self.fw_version = fw_version

    def apply_update(self, artifact: bytes, version: str,
                     sha256: str, sig_b64: str) -> Tuple[bool, str]:
        if sha256_hex(artifact) != sha256:
            return False, "checksum_mismatch"
        if not verify(self._pub, sha256, sig_b64):
            return False, "bad_signature"
        self.fw_version = version
        return True, "applied"
