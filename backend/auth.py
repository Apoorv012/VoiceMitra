"""Password hashing for the phone-app login (standard library only).

Hashes look like `scrypt$<n>$<r>$<p>$<salt hex>$<hash hex>`, so the cost can be raised later without
breaking stored ones.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_N, _R, _P, _DKLEN = 2**14, 8, 1, 32  # ~16 MB, tens of ms per hash


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                                n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except ValueError:
        return False
    return hmac.compare_digest(digest, expected)


# Checked against when the username is unknown, so a wrong username takes as long as a wrong password.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
