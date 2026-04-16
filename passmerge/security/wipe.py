"""Apagamento seguro de arquivos com dados sensíveis.

IMPORTANTE: em discos com SSD, wear-leveling e write-caching podem preservar
cópias. O método abaixo é best-effort; em SSDs modernos, recomenda-se também
criptografia de disco completa (BitLocker/FileVault/LUKS).

Estratégia:
1. Abrir o arquivo em modo read-write binário.
2. Sobrescrever 3 passes: zeros, 0xFF, aleatório.
3. fsync após cada passe.
4. Renomear para nome aleatório e então unlink (remove traços do nome no índice).
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BUFFER = 1 << 20  # 1 MiB


def secure_wipe(path: Path, passes: int = 3) -> None:
    """Sobrescreve o arquivo `passes` vezes e o remove. Idempotente se arquivo sumir."""
    path = Path(path)
    if not path.exists():
        return
    if not path.is_file():
        raise ValueError(f"{path} não é um arquivo regular")

    size = path.stat().st_size

    patterns = [b"\x00", b"\xff"]
    with open(path, "r+b", buffering=0) as f:
        for pass_idx in range(passes):
            f.seek(0)
            if pass_idx < len(patterns):
                data = patterns[pass_idx] * BUFFER
                remaining = size
                while remaining > 0:
                    chunk = data if remaining >= BUFFER else data[:remaining]
                    f.write(chunk)
                    remaining -= len(chunk)
            else:
                remaining = size
                while remaining > 0:
                    n = min(BUFFER, remaining)
                    f.write(secrets.token_bytes(n))
                    remaining -= n
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass

    # Renomeia para obscurecer o nome no índice do filesystem
    rand_name = path.with_name(secrets.token_hex(16))
    try:
        os.replace(path, rand_name)
        rand_name.unlink()
    except OSError:
        # Se falhar o rename, ao menos remove o arquivo original
        path.unlink(missing_ok=True)
