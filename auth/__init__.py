"""
Feature de Autenticación SIU SUNEDU (Login & Relogin).
Provee gestión de sesión, reutilización rápida, relogin automático y extracción de credenciales.
"""

from .config import AuthConfig, DEFAULT_CONFIG
from .storage import SessionStorage
from .authenticator import PunkuAuthenticator
from .service import AuthService

__all__ = [
    "AuthService",
    "AuthConfig",
    "DEFAULT_CONFIG",
    "SessionStorage",
    "PunkuAuthenticator",
]
