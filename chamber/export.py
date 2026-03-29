from __future__ import annotations

import os

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from chamber.models import Session


def export_markdown(session: Session) -> str:
    """Export session as a markdown string."""
    lines = [f"# Chamber Discussion: {session.topic}", ""]

    if session.personas:
        lines.append("## Panel")
        for p in session.personas:
            lines.append(f"- **{p.name}** — {p.role} ({p.expertise})")
        lines.append("")

    current_round = 0
    for msg in session.messages:
        if msg.round_number != current_round:
            current_round = msg.round_number
            lines.append(f"## Round {current_round}")
            lines.append("")

        if msg.role == "moderator":
            lines.append(f"### Moderator")
        elif msg.role == "user":
            lines.append(f"### You")
        else:
            lines.append(f"### [{msg.agent_name}]")

        lines.append("")
        lines.append(msg.content)
        lines.append("")

    return "\n".join(lines)


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from passphrase using scrypt."""
    kdf = Scrypt(salt=salt, length=32, n=2**17, r=8, p=1)
    return kdf.derive(passphrase.encode())


def export_encrypted(markdown: str, passphrase: str) -> bytes:
    """Encrypt markdown content with AES-256-GCM. Returns salt + nonce + ciphertext."""
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, markdown.encode(), None)
    return salt + nonce + ciphertext


def decrypt_export(data: bytes, passphrase: str) -> str:
    """Decrypt an encrypted export. Returns markdown string."""
    salt = data[:16]
    nonce = data[16:28]
    ciphertext = data[28:]
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()
