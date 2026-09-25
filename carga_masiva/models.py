from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class CargaMasivaRecord:
    """
    Representa un registro de carga masiva obtenido del API de SUNEDU SIU Gateway.
    Endpoint: /api/v1/soporte/archivo/listar
    """
    id_carga: int
    id_entidad: int
    entidad_nombre: str
    id_tipo_carga: int
    tipo_carga: str
    usuario_nombre: str
    fecha_carga: str
    fecha_inicio_proceso: Optional[str]
    fecha_fin_proceso: Optional[str]
    fecha_validacion_inicio: Optional[str]
    fecha_validacion_fin: Optional[str]
    estado_proceso: str
    cantidad_total: int
    cantidad_validos: int
    cantidad_observados: int
    cantidad_procesados: int
    nombre_archivo: str
    ruta_archivo: str
    extension: str
    tamanio_bytes: int
    guid_archivo: str
    completado: bool
    tiene_errores: bool
    tiene_validos: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id_carga": self.id_carga,
            "entidad": self.entidad_nombre,
            "tipo_carga": self.tipo_carga,
            "usuario": self.usuario_nombre,
            "fecha_hora_carga": self.fecha_carga,
            "fecha_inicio_proceso": self.fecha_inicio_proceso or "",
            "fecha_fin_proceso": self.fecha_fin_proceso or "",
            "fecha_validacion_inicio": self.fecha_validacion_inicio or "",
            "fecha_validacion_fin": self.fecha_validacion_fin or "",
            "estado_proceso": self.estado_proceso,
            "cantidad_total": self.cantidad_total,
            "cantidad_validos": self.cantidad_validos,
            "cantidad_observados": self.cantidad_observados,
            "cantidad_procesados": self.cantidad_procesados,
            "nombre_archivo": self.nombre_archivo,
            "ruta_archivo": self.ruta_archivo,
            "extension": self.extension,
            "tamanio_bytes": self.tamanio_bytes,
            "guid_archivo": self.guid_archivo,
            "completado": "SÍ" if self.completado else "NO",
            "tiene_errores": "SÍ" if self.tiene_errores else "NO",
            "tiene_validos": "SÍ" if self.tiene_validos else "NO",
        }


@dataclass(frozen=True)
class DetalleCargaRecord:
    """
    Representa el detalle u observación individual de un registro de carga masiva.
    """
    id_carga: int
    fila_archivo: Optional[int] = None
    codigo_error: Optional[str] = None
    descripcion_error: Optional[str] = None
    valor_observado: Optional[str] = None
    fecha_registro: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id_carga": self.id_carga,
            "fila_archivo": self.fila_archivo or "",
            "codigo_error": self.codigo_error or "",
            "descripcion_error": self.descripcion_error or "",
            "valor_observado": self.valor_observado or "",
            "fecha_registro": self.fecha_registro or "",
        }
