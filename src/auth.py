"""Autenticação da interface.

Evolução sobre o design original: a senha não fica hardcoded no código nem na
documentação — é configurada por variável de ambiente (`APP_PASSWORD` ou o hash
`APP_PASSWORD_SHA256`) e comparada em tempo constante (hmac.compare_digest).
"""

from __future__ import annotations

import hashlib
import hmac

from src.config import DEFAULT_PASSWORD_SHA256, settings


def verify_credentials(username: str, password: str) -> bool:
    username_ok = hmac.compare_digest(username.strip(), settings.app_username)
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    password_ok = hmac.compare_digest(password_hash, settings.app_password_sha256)
    return username_ok and password_ok


def using_default_password() -> bool:
    """Indica se a instalação ainda usa a senha padrão (para exibir alerta na UI)."""
    return settings.app_password_sha256 == DEFAULT_PASSWORD_SHA256
