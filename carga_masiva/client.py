import logging
from typing import Dict, List, Optional, Tuple, Any
from playwright.sync_api import BrowserContext, Page

from .models import CargaMasivaRecord

logger = logging.getLogger(__name__)


class CargaMasivaApiClient:
    """
    Cliente API autenticado de alto rendimiento para el módulo de Carga Masiva (SIU SUNEDU).
    Consume directamente el endpoint del Gateway:
    https://siugw.sunedu.gob.pe/api/v1/soporte/archivo/listar
    """

    BASE_GW_URL: str = "https://siugw.sunedu.gob.pe"
    LISTAR_URL: str = f"{BASE_GW_URL}/api/v1/soporte/archivo/listar"
    OBTENER_URL: str = f"{BASE_GW_URL}/api/v1/soporte/archivo/obtener"

    # Cabeceras requeridas por el microservicio de soporte/archivo de SUNEDU
    DEFAULT_EXTRA_HEADERS: Dict[str, str] = {
        "codigo_accion": "CON",
        "codigo_entidad": "012",
        "guid_menu": "92ae7d88-e83e-4420-8f68-ea13fa9ad88e",
        "guid_modulo": "b7c8435a-1f72-4ba3-bc04-4a9446ca3311",
        "guid_rol": "1ed6a560-fdf5-444b-b0ac-fbdfaf7dbaad",
        "guid_sistema": "01E002E4-2794-45AB-A9E3-94FEAC502550",
        "identidad": "9",
        "origin": "https://siu.sunedu.gob.pe",
        "referer": "https://siu.sunedu.gob.pe/",
    }

    def __init__(self, context: BrowserContext, page: Page):
        self.context = context
        self.page = page
        self.headers: Dict[str, str] = {}
        self._initialized = False

    def initialize_headers(self, timeout: int = 30000) -> bool:
        """
        Captura las cabeceras de autorización activas navegando a SIU.
        Intercepta el token JWT Bearer que Angular inyecta en cada petición.
        """
        if self._initialized and self.headers and "authorization" in self.headers:
            return True

        captured: Dict[str, str] = {}

        def on_request(req):
            if "authorization" in req.headers and "Bearer" in req.headers.get("authorization", ""):
                captured.update(req.headers)

        self.page.on("request", on_request)

        # Cargar ruta donde Angular inicializa la sesión y peticiones
        target_url = "https://siu.sunedu.gob.pe/academico/postulante"
        logger.info(f"Navegando a {target_url} para sincronizar tokens Bearer y cabeceras...")
        try:
            self.page.goto(target_url, wait_until="domcontentloaded", timeout=timeout)
            self.page.wait_for_selector(".data-grid-container", timeout=timeout)
            self.page.wait_for_timeout(1000)
        except Exception as e:
            logger.warning(f"Aviso al navegar para sincronizar cabeceras: {e}")

        try:
            self.page.remove_listener("request", on_request)
        except Exception:
            pass

        if captured and "authorization" in captured:
            self.headers = captured
            for k, v in self.DEFAULT_EXTRA_HEADERS.items():
                if k not in self.headers:
                    self.headers[k] = v
            self._initialized = True
            logger.info("Cabeceras y token Bearer activo capturados dinámicamente de la sesión en memoria.")
            return True

        logger.error("No se pudo capturar el token de autorización de la sesión activa.")
        return False

    def set_auth_token(self, token: str) -> None:
        """Permite configurar directamente el token Bearer y las cabeceras estándar."""
        clean_token = token.replace("Bearer ", "").strip()
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": f"Bearer {clean_token}",
            **self.DEFAULT_EXTRA_HEADERS,
        }
        self._initialized = True

    def fetch_cargas_page(
        self,
        skip: int = 0,
        page_size: int = 100,
        codigo_entidad: str = "012",
        fecha_desde: Optional[str] = None,
        id_tipo_carga: Optional[int] = None,
    ) -> Tuple[int, List[CargaMasivaRecord]]:
        """
        Consulta una página de registros de carga masiva en el Gateway de SUNEDU.
        Permite filtrar por entidad, fecha_desde y por tipo específico (filter.idTblTipoCarga).
        Retorna (total_registros, lista_de_registros).
        """
        if not self._initialized:
            self.initialize_headers()

        query_parts = [
            f"pageSize={page_size}",
            f"skip={skip}",
            "sortField=null",
            "sortDir=null",
            f"filter.codigoEntidad={codigo_entidad}",
        ]
        if id_tipo_carga is not None:
            query_parts.append(f"filter.idTblTipoCarga={id_tipo_carga}")
        if fecha_desde:
            query_parts.append(f"filter.fechaCreacionDesde={fecha_desde}")

        params = "?" + "&".join(query_parts)
        url = f"{self.LISTAR_URL}{params}"

        try:
            res = self.context.request.get(url, headers=self.headers, timeout=30000)
            if res.status != 200:
                logger.error(f"Error en API soporte/archivo/listar (HTTP {res.status}): {res.text()[:200]}")
                return 0, []

            payload = res.json()
            total_count = int(payload.get("count", 0))
            raw_items = payload.get("data", [])

            records: List[CargaMasivaRecord] = []
            for item in raw_items:
                record = CargaMasivaRecord(
                    id_carga=int(item.get("idArchivo", 0)),
                    id_entidad=int(item.get("idEntidad", 0)),
                    entidad_nombre=str(item.get("entidadNombre") or "Universidad Nacional del Altiplano").strip(),
                    id_tipo_carga=int(item.get("idTblTipoCarga", 0)),
                    tipo_carga=str(item.get("dscTipoCarga") or "Sin Tipo").strip(),
                    usuario_nombre=str(item.get("usuarioCreacionNombre") or "").strip(),
                    fecha_carga=str(item.get("fechaCreacion") or "").strip(),
                    fecha_inicio_proceso=item.get("fechaProcesamientoInicio"),
                    fecha_fin_proceso=item.get("fechaProcesamientoFin"),
                    fecha_validacion_inicio=item.get("fechaValidacionInicio"),
                    fecha_validacion_fin=item.get("fechaValidacionFin"),
                    estado_proceso=str(item.get("dscEstadoCarga") or "").strip(),
                    cantidad_total=int(item.get("cantidadRegistrosTotal") or 0),
                    cantidad_validos=int(item.get("cantidadRegistrosValidos") or 0),
                    cantidad_observados=int(item.get("cantidadRegistrosObservados") or 0),
                    cantidad_procesados=int(item.get("cantidadRegistrosProcesados") or 0),
                    nombre_archivo=str(item.get("nombre") or "").strip(),
                    ruta_archivo=str(item.get("ruta") or "").strip(),
                    extension=str(item.get("extension") or "").strip(),
                    tamanio_bytes=int(item.get("tamanio") or 0),
                    guid_archivo=str(item.get("guidArchivo") or "").strip(),
                    completado=bool(item.get("completed", False)),
                    tiene_errores=bool(item.get("hasErrors", False)),
                    tiene_validos=bool(item.get("hasValids", False)),
                )
                records.append(record)

            return total_count, records

        except Exception as e:
            logger.error(f"Excepción en fetch_cargas_page (Skip={skip}): {e}")
            return 0, []

    DESCARGAR_ORIGINAL_URL: str = f"{BASE_GW_URL}/s/v1/archivo/descargar"
    DESCARGAR_VALIDOS_URL: str = f"{BASE_GW_URL}/s/v1/archivo/descargarValidos"
    DESCARGAR_OBSERVADOS_URL: str = f"{BASE_GW_URL}/s/v1/archivo/descargarObservados"

    def download_file(
        self,
        endpoint_url: str,
        guid_archivo: str,
        target_dir: Any,
        id_carga: int,
        fallback_prefix: str = "ARCHIVO",
    ) -> Optional[Any]:
        """
        Descarga un archivo Excel desde el endpoint indicado usando guid_archivo como 'peticion'.
        Almacena el archivo en target_dir con prefijo id_carga.
        """
        import re
        import urllib.parse
        from pathlib import Path

        if not guid_archivo:
            return None

        if not self._initialized:
            self.initialize_headers()

        target_path_dir = Path(target_dir)
        target_path_dir.mkdir(parents=True, exist_ok=True)

        url = f"{endpoint_url}?peticion={guid_archivo}"
        try:
            res = self.context.request.get(url, headers=self.headers, timeout=60000)
            if res.status != 200:
                logger.warning(f"No disponible para descarga (HTTP {res.status}): {url}")
                return None

            body = res.body()
            if not body or len(body) == 0:
                logger.warning(f"Contenido vacío recibido desde {url}")
                return None

            # Extraer nombre original de archivo desde Content-Disposition
            cd = res.headers.get("content-disposition", "")
            filename = None
            if "filename*=" in cd:
                m = re.search(r"filename\*=UTF-8''([^;]+)", cd)
                if m:
                    filename = urllib.parse.unquote(m.group(1)).strip('"\' ')
            if not filename and "filename=" in cd:
                m = re.search(r'filename="?([^";]+)"?', cd)
                if m:
                    filename = m.group(1).strip('"\' ')

            if not filename:
                filename = f"{fallback_prefix}.xlsx"

            clean_filename = f"{id_carga}_{filename}"
            output_file = target_path_dir / clean_filename

            with open(output_file, "wb") as f:
                f.write(body)

            logger.info(f"✔ Descargado exitosamente: {clean_filename} ({len(body)} bytes)")
            return output_file

        except Exception as e:
            logger.error(f"Error al descargar archivo desde {url}: {e}")
            return None

    def download_original(self, guid_archivo: str, target_dir: Any, id_carga: int, fallback_nombre: str = "") -> Optional[Any]:
        """Descarga el archivo Excel original subido (subida total)."""
        return self.download_file(self.DESCARGAR_ORIGINAL_URL, guid_archivo, target_dir, id_carga, fallback_nombre or "ORIGINAL")

    def download_validos(self, guid_archivo: str, target_dir: Any, id_carga: int) -> Optional[Any]:
        """Descarga el archivo Excel de registros válidos."""
        return self.download_file(self.DESCARGAR_VALIDOS_URL, guid_archivo, target_dir, id_carga, "VALIDOS")

    def download_observados(self, guid_archivo: str, target_dir: Any, id_carga: int) -> Optional[Any]:
        """Descarga el archivo Excel de registros observados / errores."""
        return self.download_file(self.DESCARGAR_OBSERVADOS_URL, guid_archivo, target_dir, id_carga, "OBSERVADOS")
