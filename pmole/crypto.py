# MIT License

# Copyright (c) 2025 ramsy0dev

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
AES-256-GCM encryption for .pm archives.

Encrypted archive layout
------------------------
Offset  Size  Field
0       4     magic  b"PME\\x01"
4       16    salt   PBKDF2 salt (random)
20      12    nonce  AES-GCM nonce (random)
32      N+16  ciphertext + authentication tag  (N = plaintext length)
"""

import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_ENC_MAGIC        = b"PME\x01"
_SALT_SIZE        = 16
_NONCE_SIZE       = 12
_PBKDF2_ITERS     = 260_000   # OWASP 2023 recommendation for PBKDF2-HMAC-SHA256


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_archive(data: bytes, password: str) -> bytes:
    """
    Encrypt *data* with AES-256-GCM derived from *password*.
    Returns the full encrypted envelope (magic + salt + nonce + ciphertext+tag).
    """
    if not password:
        raise ValueError("Password must not be empty.")
    salt  = os.urandom(_SALT_SIZE)
    nonce = os.urandom(_NONCE_SIZE)
    key   = _derive_key(password, salt)
    ct    = AESGCM(key).encrypt(nonce, data, None)   # ct includes the 16-byte GCM tag
    return _ENC_MAGIC + salt + nonce + ct


def decrypt_archive(data: bytes, password: str) -> bytes:
    """
    Decrypt an encrypted archive envelope.
    Raises ValueError if the magic is wrong, the password is incorrect, or the
    ciphertext is corrupted (GCM authentication failure).
    """
    if data[:4] != _ENC_MAGIC:
        raise ValueError("Not an encrypted .pm archive.")
    salt       = data[4:20]
    nonce      = data[20:32]
    ciphertext = data[32:]
    key = _derive_key(password, salt)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Incorrect password or corrupted archive.") from None
