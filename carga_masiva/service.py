import logging
from collections import Counter
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright

from auth import AuthService
from .client import CargaMasivaApiClient
from .persistence import CargaMasivaPersistenceManager

logger = logging.getLogger(__name__)


class CargaMasivaService:
    """
    Servicio orquestador para la consulta y sincronización de Cargas Masivas de SUNEDU SIU.
    Aplica principios SOLID:
    - SRP: Orquesta autenticación, cliente API y persistencia segregada por tipo de carga.
    - Resiliencia: Reanudación automática con Checkpoints, tolerancia a fallos.
    """

    TIPO_CARGA_MAP: Dict[int, str] = {
        1: "Datos de ingreso",
        2: "Datos de matrícula",
        24: "Inscripción de grados nacionales",
        26: "Datos de postulante",
        27: "Personal Docente",
        31: "Docente por Ciclo Académico",
        32: "Administrativo por Gestión Administrativa",
    }

    TIPO_CARGA_TO_ID: Dict[str, int] = {
        "1": 1,
        "datos de ingreso": 1,
        "ingreso": 1,
        "ingresos": 1,
        "2": 2,
        "datos de matrícula": 2,
        "datos de matricula": 2,
        "matrícula": 2,
        "matricula": 2,
        "matriculas": 2,
        "24": 24,
        "inscripción de grados nacionales": 24,
        "inscripcion de grados nacionales": 24,
        "grados": 24,
        "26": 26,
        "datos de postulante": 26,
        "postulante": 26,
        "postulantes": 26,
        "27": 27,
        "personal docente": 27,
        "docente": 27,
        "docentes": 27,
        "31": 31,
        "docente por ciclo académico": 31,
        "docente por ciclo academico": 31,
        "32": 32,
        "administrativo por gestión administrativa": 32,
        "administrativo por gestion administrativa": 32,
        "administrativo": 32,
        "administrativos": 32,
    }

    def __init__(
        self,
        auth_service: Optional[AuthService] = None,
        persistence: Optional[CargaMasivaPersistenceManager] = None,
    ):
        self.auth_service = auth_service or AuthService()
        self.persistence = persistence or CargaMasivaPersistenceManager()

    def resolve_tipo_id(self, tipo: Optional[Any]) -> Optional[int]:
        """Resuelve un string o número a su idTblTipoCarga oficial de SUNEDU."""
        if tipo is None:
            return None
        if isinstance(tipo, int):
            return tipo
        cleaned = str(tipo).strip().lower()
        if cleaned.isdigit():
            return int(cleaned)
        return self.TIPO_CARGA_TO_ID.get(cleaned)

    def sync_historial(
        self,
        tipo_carga: Optional[str] = None,
        id_tipo_carga: Optional[int] = None,
        fecha_desde: Optional[str] = "2021-01-01T00:00:00-05:00",
        page_size: int = 100,
        resume: bool = True,
        headless: bool = True,
    ) -> Dict[str, Any]:
        """
        Descarga el historial de Cargas Masivas.
        Permite filtrar directamente por tipo (idTblTipoCarga o nombre: ej. 26 postulantes, 2 matricula)
        y por fecha inicial.
        """
        # Si no se especifica tipo, sincronizar las dos categorías de interés: Postulantes y Matrícula
        if id_tipo_carga is None and tipo_carga is None:
            tipos_a_sincronizar = [(26, "Datos de postulante"), (2, "Datos de matrícula")]
            res_total = {"success": True, "total_saved": 0, "por_tipo": {}}
            for tid, tnom in tipos_a_sincronizar:
                res = self.sync_historial(
                    tipo_carga=tnom,
                    id_tipo_carga=tid,
                    fecha_desde=fecha_desde,
                    page_size=page_size,
                    resume=resume,
                    headless=headless,
                )
                res_total["total_saved"] += res.get("total_saved", 0)
                res_total["por_tipo"].update(res.get("por_tipo", {}))
            return res_total

        # Resolver id_tipo_carga si se pasó como texto o nombre
        if id_tipo_carga is None and tipo_carga is not None:
            id_tipo_carga = self.resolve_tipo_id(tipo_carga)

        nombre_tipo_filtro = self.TIPO_CARGA_MAP.get(id_tipo_carga, tipo_carga) if id_tipo_carga else "Todos los tipos"
        filter_key = f"tipo_{id_tipo_carga}" if id_tipo_carga else None

        print("\n" + "=" * 65)
        print("   INICIANDO EXTRACCIÓN DE HISTORIAL DE CARGAS MASIVAS (SIU SUNEDU)")
        if id_tipo_carga:
            print(f"   Filtro Tipo (idTblTipoCarga): {id_tipo_carga} ({nombre_tipo_filtro})")
        else:
            print(f"   Filtro Tipo: {nombre_tipo_filtro}")
        if fecha_desde:
            print(f"   Filtro fecha: Desde {fecha_desde[:10]}")
        else:
            print("   Filtro fecha: Todo el histórico disponible")
        print("=" * 65)

        # 1. Checkpoint
        skip = 0
        current_page = 1
        if resume:
            ckpt = self.persistence.load_checkpoint(filter_key=filter_key)
            if ckpt and ckpt.get("last_skip") is not None:
                skip = ckpt["last_skip"] + ckpt["page_size"]
                current_page = ckpt["last_page"] + 1
                logger.info(
                    f"Reanudando desde Checkpoint: Página {current_page} (Skip={skip}) | "
                    f"Ya acumulados: {ckpt.get('total_saved', 0)} de {ckpt.get('total_records', 0)}"
                )

        total_saved_in_session = 0
        tipos_counter = Counter()

        with self.auth_service.get_authenticated_browser(headless=headless) as (browser, context, page):
            client = CargaMasivaApiClient(context, page)
            if not client.initialize_headers():
                logger.error("No se pudieron inicializar las cabeceras de API de SUNEDU.")
                return {"success": False, "total_saved": 0}

            logger.info("Cabeceras sincronizadas. Iniciando descarga de registros...")

            while True:
                logger.info(f"Descargando Página {current_page} (Skip={skip}, PageSize={page_size})...")
                total_records, records = client.fetch_cargas_page(
                    skip=skip,
                    page_size=page_size,
                    codigo_entidad="012",
                    fecha_desde=fecha_desde,
                    id_tipo_carga=id_tipo_carga,
                )

                if not records:
                    logger.info("No se recibieron más registros o se llegó al final de la paginación.")
                    break

                for r in records:
                    tipos_counter[r.tipo_carga] += 1

                saved_count = self.persistence.save_batch(
                    records=records,
                    skip=skip,
                    page_num=current_page,
                    total_records=total_records,
                    page_size=page_size,
                    filter_key=filter_key,
                )
                total_saved_in_session += saved_count

                total_pages = (total_records // page_size) + (1 if total_records % page_size > 0 else 0)
                logger.info(
                    f"✔ Progreso: Página {current_page}/{total_pages} | "
                    f"Recibidos: {len(records)} | +{saved_count} nuevos guardados."
                )

                if skip + len(records) >= total_records:
                    logger.info("¡Se completó la extracción de los registros solicitados!")
                    break

                skip += page_size
                current_page += 1

        print("\n" + "=" * 65)
        print("          RESUMEN POR TIPO DE CARGA MASIVA (2021 EN ADELANTE)")
        print("=" * 65)
        for tipo, count in tipos_counter.most_common():
            dir_tipo = self.persistence.get_dir_for_tipo(tipo)
            print(f"  • {tipo:30}: {count:5} registros -> [{dir_tipo.name}/historial_cargas.csv]")

        print("-" * 65)
        print(f"  Total nuevos guardados en sesión: {total_saved_in_session}")
        print(f"  Archivo consolidado general     : {self.persistence.consolidado_csv.name}")
        print("=" * 65 + "\n")

        return {
            "success": True,
            "total_saved": total_saved_in_session,
            "por_tipo": dict(tipos_counter),
        }

    def download_excels(
        self,
        tipo_carga: Optional[str] = None,
        descargar_original: bool = True,
        descargar_validos: bool = True,
        descargar_observados: bool = True,
        max_cargas: Optional[int] = None,
        delay_seconds: float = 0.1,
        headless: bool = True,
    ) -> Dict[str, int]:
        """
        Descarga los archivos Excel físicos organizados en 3 subcarpetas por Tipo de Carga:
        - originales/: Archivo Excel de subida total
        - validos/   : Archivo Excel con registros válidos (si cantidad_validos > 0)
        - observados/: Archivo Excel con observaciones / errores (si cantidad_observados > 0)
        """
        import time

        cargas = self.persistence.get_cargas_from_csv(tipo_carga)
        if not cargas:
            logger.warning("No se encontraron registros de cargas masivas en el CSV. Ejecuta primero --cargas para sincronizar el historial.")
            return {"originales": 0, "validos": 0, "observados": 0}

        total_a_procesar = min(len(cargas), max_cargas) if max_cargas else len(cargas)
        cargas_slice = cargas[:total_a_procesar]

        print("\n" + "=" * 65)
        print("     INICIANDO DESCARGA DE ARCHIVOS EXCEL (CARGA MASIVA)")
        print(f"     Filtro tipo: {tipo_carga or 'Todos los tipos'}")
        print(f"     Total de cargas a evaluar: {total_a_procesar}")
        print("=" * 65)

        stats = {
            "originales_descargados": 0,
            "validos_descargados": 0,
            "observados_descargados": 0,
            "omitidos_existentes": 0,
            "no_disponibles": 0,
        }

        with self.auth_service.get_authenticated_browser(headless=headless) as (browser, context, page):
            client = CargaMasivaApiClient(context, page)
            if not client.initialize_headers():
                logger.error("No se pudieron inicializar las cabeceras de API para descargas.")
                return stats

            for idx, c in enumerate(cargas_slice, start=1):
                id_carga = int(c.get("id_carga", 0))
                guid = str(c.get("guid_archivo", "")).strip()
                tipo = str(c.get("tipo_carga", "otros")).strip()
                nombre_base = str(c.get("nombre_archivo", "")).strip()
                cant_val = int(c.get("cantidad_validos") or 0)
                cant_obs = int(c.get("cantidad_observados") or 0)
                tiene_val = str(c.get("tiene_validos", "")).upper() == "SÍ"
                tiene_err = str(c.get("tiene_errores", "")).upper() == "SÍ"

                dirs = self.persistence.get_dirs_for_tipo(tipo)

                logger.info(f"[{idx}/{total_a_procesar}] Procesando Carga #{id_carga} ({tipo}) | Válidos: {cant_val}, Observados: {cant_obs}")

                # 1. Descargar Original (Subida total)
                if descargar_original and guid:
                    orig_existentes = list(dirs["originales"].glob(f"{id_carga}_*"))
                    if orig_existentes:
                        stats["omitidos_existentes"] += 1
                    else:
                        out = client.download_original(guid, dirs["originales"], id_carga, nombre_base)
                        if out:
                            stats["originales_descargados"] += 1
                        else:
                            stats["no_disponibles"] += 1

                # 2. Descargar Válidos (solo si hay válidos)
                if descargar_validos and guid and (cant_val > 0 or tiene_val):
                    val_existentes = list(dirs["validos"].glob(f"{id_carga}_*"))
                    if val_existentes:
                        stats["omitidos_existentes"] += 1
                    else:
                        out = client.download_validos(guid, dirs["validos"], id_carga)
                        if out:
                            stats["validos_descargados"] += 1
                        else:
                            stats["no_disponibles"] += 1

                # 3. Descargar Observados (solo si hay observaciones/errores)
                if descargar_observados and guid and (cant_obs > 0 or tiene_err):
                    obs_existentes = list(dirs["observados"].glob(f"{id_carga}_*"))
                    if obs_existentes:
                        stats["omitidos_existentes"] += 1
                    else:
                        out = client.download_observados(guid, dirs["observados"], id_carga)
                        if out:
                            stats["observados_descargados"] += 1
                        else:
                            stats["no_disponibles"] += 1

                if delay_seconds > 0:
                    time.sleep(delay_seconds)

        print("\n" + "=" * 65)
        print("          RESUMEN DE DESCARGA DE ARCHIVOS EXCEL")
        print("=" * 65)
        print(f"  • Archivos originales descargados  : {stats['originales_descargados']}")
        print(f"  • Archivos válidos descargados      : {stats['validos_descargados']}")
        print(f"  • Archivos observados descargados   : {stats['observados_descargados']}")
        print(f"  • Omitidos (ya existían en disco)   : {stats['omitidos_existentes']}")
        print("=" * 65 + "\n")

        return stats
