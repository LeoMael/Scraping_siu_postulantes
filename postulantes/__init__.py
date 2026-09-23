"""
Feature de Extracción de Postulantes en SIU SUNEDU.
Incluye persistencia en dos CSVs relacionados (listado y detalle),
tolerancia a fallos con checkpoints y consumo directo de las APIs internas.
"""

from .models import (
    PostulanteListadoRecord,
    PostulanteDetalleRecord,
    CheckpointListado,
    CheckpointDetalle,
)
from .client import SuneduApiClient
from .persistence import CsvPersistenceManager
from .service import PostulantesService

__all__ = [
    "PostulanteListadoRecord",
    "PostulanteDetalleRecord",
    "CheckpointListado",
    "CheckpointDetalle",
    "SuneduApiClient",
    "CsvPersistenceManager",
    "PostulantesService",
]
