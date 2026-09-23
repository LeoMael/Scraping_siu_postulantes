from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class PostulanteListadoRecord:
    """
    Entidad que representa un registro en la tabla maestra (listado) de postulantes.
    Archivo de destino: postulantes_listado.csv
    """
    id_postulante: int
    guid: str
    row_num: int
    id_entidad: int
    entidad: str
    id_filial: int
    filial: str
    id_nivel_academico: int
    nivel_academico: str
    id_tipo_proceso: int
    tipo_proceso: str
    proceso_admision: str
    numero_convocatoria: str
    fecha_convocatorias: str
    id_persona: int
    documento_identidad: str
    postulante: str
    id_unidad: int
    unidad: str
    id_programa: int
    programa: str
    es_ingresante: bool
    id_modalidad_ingreso: int
    modalidad_ingreso: str
    fecha_registro: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id_postulante": self.id_postulante,
            "guid": self.guid,
            "row_num": self.row_num,
            "id_entidad": self.id_entidad,
            "entidad": self.entidad,
            "id_filial": self.id_filial,
            "filial": self.filial,
            "id_nivel_academico": self.id_nivel_academico,
            "nivel_academico": self.nivel_academico,
            "tipo_proceso": self.tipo_proceso,
            "proceso_admision": self.proceso_admision,
            "numero_convocatoria": self.numero_convocatoria,
            "fecha_convocatorias": self.fecha_convocatorias,
            "id_persona": self.id_persona,
            "documento_identidad": self.documento_identidad,
            "postulante": self.postulante,
            "unidad": self.unidad,
            "programa": self.programa,
            "es_ingresante": "SÍ" if self.es_ingresante else "NO",
            "modalidad_ingreso": self.modalidad_ingreso,
            "fecha_registro": self.fecha_registro,
        }


@dataclass(frozen=True)
class PostulanteDetalleRecord:
    """
    Entidad que representa el detalle profundo obtenido del modal / API de la lupa.
    Se relaciona con la tabla maestra mediante id_postulante y guid.
    Archivo de destino: postulantes_detalle.csv
    """
    id_postulante: int
    guid: str
    id_persona: int
    tipo_documento: str
    numero_documento: str
    nombres: str
    primer_apellido: str
    segundo_apellido: str
    solo_un_apellido: bool
    sexo: str
    apellido_casada: Optional[str]
    fecha_nacimiento: str
    pais_nacimiento: str
    nacionalidad: str
    ubigeo_nacimiento: str
    ubigeo_domicilio: str
    celular: str
    correo_personal: str
    fecha_postulacion: str
    puntaje_obtenido: str
    modalidad_ingreso: str
    modalidad_estudio: str
    es_ingresante: bool
    segunda_opcion: str
    tercera_opcion: str
    condicion_discapacidad: bool
    habla_lengua_indigena: Optional[str]
    lengua_indigena: Optional[str]
    se_siente_parte_de: Optional[str]
    pueblo_indigena: Optional[str]
    colegio_nombre: Optional[str]
    colegio_gestion: Optional[str]
    colegio_anio_egreso: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id_postulante": self.id_postulante,
            "guid": self.guid,
            "id_persona": self.id_persona,
            "tipo_documento": self.tipo_documento,
            "numero_documento": self.numero_documento,
            "nombres": self.nombres,
            "primer_apellido": self.primer_apellido,
            "segundo_apellido": self.segundo_apellido,
            "solo_un_apellido": "SÍ" if self.solo_un_apellido else "NO",
            "sexo": self.sexo,
            "apellido_casada": self.apellido_casada or "",
            "fecha_nacimiento": self.fecha_nacimiento,
            "pais_nacimiento": self.pais_nacimiento,
            "nacionalidad": self.nacionalidad,
            "ubigeo_nacimiento": self.ubigeo_nacimiento,
            "ubigeo_domicilio": self.ubigeo_domicilio,
            "celular": self.celular,
            "correo_personal": self.correo_personal,
            "fecha_postulacion": self.fecha_postulacion,
            "puntaje_obtenido": self.puntaje_obtenido,
            "modalidad_ingreso": self.modalidad_ingreso,
            "modalidad_estudio": self.modalidad_estudio,
            "es_ingresante": "SÍ" if self.es_ingresante else "NO",
            "segunda_opcion": self.segunda_opcion,
            "tercera_opcion": self.tercera_opcion,
            "condicion_discapacidad": "SÍ" if self.condicion_discapacidad else "NO",
            "habla_lengua_indigena": self.habla_lengua_indigena or "",
            "lengua_indigena": self.lengua_indigena or "",
            "se_siente_parte_de": self.se_siente_parte_de or "",
            "pueblo_indigena": self.pueblo_indigena or "",
            "colegio_nombre": self.colegio_nombre or "",
            "colegio_gestion": self.colegio_gestion or "",
            "colegio_anio_egreso": self.colegio_anio_egreso or "",
        }


@dataclass(frozen=True)
class CheckpointListado:
    """Estado de reanudación para la tabla maestra de postulantes."""
    last_skip: int
    last_page: int
    page_size: int
    total_records: int
    total_saved: int
    last_id_postulante: Optional[int]
    updated_at: str


@dataclass(frozen=True)
class CheckpointDetalle:
    """Estado de reanudación para la extracción de detalles de postulantes."""
    total_saved: int
    last_id_postulante: Optional[int]
    updated_at: str
