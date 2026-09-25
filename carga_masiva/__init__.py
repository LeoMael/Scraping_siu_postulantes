"""
Módulo de Carga Masiva - SIU SUNEDU.
Encargado de la consulta del historial, estado y descarga de reportes/observaciones.
"""

from .models import CargaMasivaRecord, DetalleCargaRecord
from .client import CargaMasivaApiClient
from .persistence import CargaMasivaPersistenceManager
from .service import CargaMasivaService

__all__ = [
    "CargaMasivaRecord",
    "DetalleCargaRecord",
    "CargaMasivaApiClient",
    "CargaMasivaPersistenceManager",
    "CargaMasivaService",
]
