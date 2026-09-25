import logging
from typing import Dict, List, Optional, Tuple, Any
from playwright.sync_api import BrowserContext, Page

from .models import PostulanteListadoRecord, PostulanteDetalleRecord

logger = logging.getLogger(__name__)


class SuneduApiClient:
    """
    Cliente API autenticado de alto rendimiento para SIU SUNEDU.
    Utiliza los tokens y cabeceras capturados de la sesión activa para realizar
    consultas directas a la API gateway de SUNEDU (siugw.sunedu.gob.pe).
    """

    BASE_GW_URL: str = "https://siugw.sunedu.gob.pe"
    LISTAR_URL: str = f"{BASE_GW_URL}/api/academico/postulante/ListarPostulantes"
    DETALLE_URL: str = f"{BASE_GW_URL}/api/academico/postulante"
    COLEGIO_URL: str = f"{BASE_GW_URL}/api/academico/postulante/GetDatosColegio"

    def __init__(self, context: BrowserContext, page: Page):
        self.context = context
        self.page = page
        self.headers: Dict[str, str] = {}
        self._initialized = False

    def initialize_headers(self, timeout: int = 30000) -> bool:
        """
        Navega a la sección de postulantes y captura las cabeceras exactas
        que Angular y SUNEDU Gateway usan (JWT Bearer, IDs de rol, menú, etc.).
        """
        if self._initialized and self.headers:
            return True

        captured: Dict[str, str] = {}

        def on_request(req):
            if "ListarPostulantes" in req.url and "authorization" in req.headers:
                captured.update(req.headers)

        self.page.on("request", on_request)

        target_url = "https://siu.sunedu.gob.pe/academico/postulante"
        if target_url not in self.page.url:
            logger.info("Cargando ruta de postulantes para sincronizar cabeceras de API...")
            self.page.goto(target_url, wait_until="domcontentloaded", timeout=timeout)

        # Esperar a que la tabla aparezca
        self.page.wait_for_selector(".data-grid-container", timeout=timeout)
        self.page.wait_for_timeout(1500)

        # Remover listener
        try:
            self.page.remove_listener("request", on_request)
        except Exception:
            pass

        if not captured or "authorization" not in captured:
            logger.error("No se pudieron capturar las credenciales y cabeceras de la API.")
            return False

        self.headers = captured
        self._initialized = True
        logger.info("Cabeceras y token de API SUNEDU Gateway capturados exitosamente.")
        return True

    def fetch_listado_page(
        self,
        skip: int = 0,
        page_size: int = 100,
        id_entidad: int = 9,
    ) -> Tuple[int, List[PostulanteListadoRecord]]:
        """
        Consulta un lote paginado de la tabla maestra de postulantes.
        Retorna (total_registros_en_sistema, lista_de_registros).
        """
        if not self._initialized:
            self.initialize_headers()

        params = (
            f"?PageSize={page_size}"
            f"&Skip={skip}"
            f"&SortField=fechaRegistro"
            f"&SortDir=desc"
            f"&Filter.IdsEntidad={id_entidad}"
            f"&Filter.IdsFilial="
            f"&Filter.IdsNivelAcademico="
            f"&Filter.IdsTipoProcesoAdmision="
            f"&Filter.anioPeriodo="
            f"&Filter.numeroPeriodo="
            f"&Filter.numerosConvocatorias="
            f"&Filter.IdsEntidadUnidad="
            f"&Filter.IdsEntidadPrograma="
            f"&Filter.IdsModalidadIngreso="
            f"&Filter.IdsPersona="
            f"&Filter.EsIngresante="
            f"&Filter.FechaInicioRegistro="
            f"&Filter.FechaFinRegistro="
        )
        url = f"{self.LISTAR_URL}{params}"

        try:
            res = self.context.request.get(url, headers=self.headers, timeout=30000)
            if res.status != 200:
                logger.error(f"Error en API ListarPostulantes (HTTP {res.status}): {res.text()[:200]}")
                return 0, []

            payload = res.json()
            total_count = int(payload.get("count", 0))
            raw_items = payload.get("data", [])

            records: List[PostulanteListadoRecord] = []
            for item in raw_items:
                es_ing = str(item.get("esIngresante", "")).strip().upper() in ("SI", "SÍ", "1", "TRUE")
                record = PostulanteListadoRecord(
                    id_postulante=int(item.get("idPostulante", 0)),
                    guid=str(item.get("guid", "")),
                    row_num=int(item.get("rowNum", 0)),
                    id_entidad=int(item.get("idEntidad", id_entidad)),
                    entidad=str(item.get("entidad", "")),
                    id_filial=int(item.get("idFilial", 0)),
                    filial=str(item.get("filial", "")),
                    id_nivel_academico=int(item.get("idTblNivelAcademico", 0)),
                    nivel_academico=str(item.get("nivelAcademico", "")),
                    id_tipo_proceso=int(item.get("idTblTipoProceso", 0)),
                    tipo_proceso=str(item.get("tipoProceso", "")),
                    proceso_admision=str(item.get("procesoAdmision", "")),
                    numero_convocatoria=str(item.get("numeroConvocatoria", "")),
                    fecha_convocatorias=str(item.get("fechaConvocatorias", "")),
                    id_persona=int(item.get("idPersona", 0)),
                    documento_identidad=str(item.get("documentoIdentidad", "")).strip(),
                    postulante=str(item.get("postulante", "")).strip(),
                    id_unidad=int(item.get("idEntidadUnidadPrimeraOp", 0)),
                    unidad=str(item.get("unidad", "")).strip(),
                    id_programa=int(item.get("idEntidadProgramaPrimeraOp", 0)),
                    programa=str(item.get("programa", "")).strip(),
                    es_ingresante=es_ing,
                    id_modalidad_ingreso=int(item.get("idTblModalidadIngreso", 0)),
                    modalidad_ingreso=str(item.get("modalidadIngreso", "")).strip(),
                    fecha_registro=str(item.get("fechaRegistro", "")).strip(),
                )
                records.append(record)

            return total_count, records

        except Exception as e:
            logger.error(f"Excepción en fetch_listado_page (Skip={skip}): {e}")
            return 0, []

    def fetch_detalle(
        self,
        guid: str,
        id_postulante: int,
        id_persona: int,
        consultar_colegio: bool = True,
    ) -> Optional[PostulanteDetalleRecord]:
        """
        Consulta la API de detalle (modal de la lupa) para un postulante por su GUID.
        Opcionalmente consulta los datos de colegio si están disponibles.
        """
        if not self._initialized:
            self.initialize_headers()

        url = f"{self.DETALLE_URL}/{guid}"

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                res = self.context.request.get(url, headers=self.headers, timeout=30000)
                if res.status == 200:
                    data = res.json()

                    # Datos de colegio (opcional)
                    nro_doc = str(data.get("numeroDocumento", "")).strip()
                    colegio_nombre = None
                    colegio_gestion = None
                    colegio_egreso = None

                    if consultar_colegio and nro_doc:
                        colegio_data = self.fetch_datos_colegio(nro_doc)
                        if colegio_data and isinstance(colegio_data, dict) and "message" not in colegio_data:
                            colegio_nombre = colegio_data.get("nombreColegio") or colegio_data.get("cenEdu")
                            colegio_gestion = colegio_data.get("gestion") or colegio_data.get("tipoGestion")
                            colegio_egreso = str(colegio_data.get("anioEgreso", "")) if colegio_data.get("anioEgreso") else None

                    es_ing = bool(data.get("esIngresante", False))
                    discapacidad = bool(data.get("condicionDiscapacidad", False))
                    solo_un_ape = bool(data.get("soloUnApellido", False))

                    return PostulanteDetalleRecord(
                        id_postulante=id_postulante,
                        guid=guid,
                        id_persona=id_persona or int(data.get("idPersona", 0)),
                        tipo_documento=str(data.get("tipoDocumento", "")),
                        numero_documento=nro_doc,
                        nombres=str(data.get("nombres", "")).strip(),
                        primer_apellido=str(data.get("primerApellido", "")).strip(),
                        segundo_apellido=str(data.get("segundoApellido", "")).strip(),
                        solo_un_apellido=solo_un_ape,
                        sexo=str(data.get("sexo", "")).strip(),
                        apellido_casada=data.get("apellidoCasada"),
                        fecha_nacimiento=str(data.get("fechaNacimiento", "")).split("T")[0],
                        pais_nacimiento=str(data.get("paisNacimiento", "")).strip(),
                        nacionalidad=str(data.get("nacionalidad", "")).strip(),
                        ubigeo_nacimiento=str(data.get("textUbigeoNacimiento", "")).strip(),
                        ubigeo_domicilio=str(data.get("textUbigeoDomicilio", "")).strip(),
                        celular=str(data.get("celular", "")).strip(),
                        correo_personal=str(data.get("correoPersonal", "")).strip(),
                        fecha_postulacion=str(data.get("fechaPostulacion", "")).split("T")[0],
                        puntaje_obtenido=str(data.get("puntajeObtenido", "")).strip(),
                        modalidad_ingreso=str(data.get("modalidadIngreso", "")).strip(),
                        modalidad_estudio=str(data.get("modalidadEstudio", "")).strip(),
                        es_ingresante=es_ing,
                        segunda_opcion=str(data.get("textUnidadProgramaSegundaOP", "")).strip(),
                        tercera_opcion=str(data.get("textUnidadProgramaTerceraOP", "")).strip(),
                        condicion_discapacidad=discapacidad,
                        habla_lengua_indigena=str(data.get("idTblHablaLenguaIndigena", "")) if data.get("idTblHablaLenguaIndigena") else None,
                        lengua_indigena=str(data.get("idLenguaIndigenaOriginaria", "")) if data.get("idLenguaIndigenaOriginaria") else None,
                        se_siente_parte_de=str(data.get("idTblSeSienteParteDe", "")) if data.get("idTblSeSienteParteDe") else None,
                        pueblo_indigena=str(data.get("idPuebloIndigenaOriginario", "")) if data.get("idPuebloIndigenaOriginario") else None,
                        colegio_nombre=colegio_nombre,
                        colegio_gestion=colegio_gestion,
                        colegio_anio_egreso=colegio_egreso,
                    )
                elif res.status in (401, 403):
                    logger.warning(f"Sesión expirada (HTTP {res.status}), renovando cabeceras...")
                    self.initialize_headers()
                else:
                    logger.warning(f"Intento {attempt}/{max_retries} no exitoso para GUID {guid} (HTTP {res.status})")

            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Reintento {attempt}/{max_retries} para GUID {guid} tras error ({e}). Esperando...")
                    import time
                    time.sleep(1.5 * attempt)
                else:
                    logger.warning(f"Error definitivo en {guid} tras {max_retries} intentos: {e}. Continuando con el siguiente registro...")
                    return None

        return None

    def fetch_datos_colegio(self, numero_documento: str) -> Optional[Dict[str, Any]]:
        """Consulta los datos de colegio por número de documento."""
        if not self._initialized or not numero_documento:
            return None
        url = f"{self.COLEGIO_URL}?NumeroDocumento={numero_documento}"
        try:
            res = self.context.request.get(url, headers=self.headers, timeout=10000)
            if res.status == 200:
                return res.json()
        except Exception:
            pass
        return None
