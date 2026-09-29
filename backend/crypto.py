"""Firmware integrity: SHA-256 checksum + Ed25519 signature over the checksum."""
from __future__ import annotations

import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_keypair():
    """Return (private_key, public_key)."""
    priv = Ed25519PrivateKey.generate()
    return priv, priv.public_key()


def sign(priv: Ed25519PrivateKey, sha256_hex_str: str) -> str:
    """Sign the checksum string; return base64 signature."""
    return base64.b64encode(priv.sign(sha256_hex_str.encode())).decode()


def verify(pub: Ed25519PublicKey, sha256_hex_str: str, sig_b64: str) -> bool:
    try:
        pub.verify(base64.b64decode(sig_b64), sha256_hex_str.encode())
        return True
    except (InvalidSignature, ValueError):
        return False
