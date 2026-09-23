import time
import logging
from typing import Optional, List
from playwright.sync_api import Browser, BrowserContext, Page

from auth import AuthService
from .models import PostulanteListadoRecord, PostulanteDetalleRecord
from .client import SuneduApiClient
from .persistence import CsvPersistenceManager

logger = logging.getLogger(__name__)


class PostulantesService:
    """
    Servicio integral para la extracción de Postulantes en SIU SUNEDU.
    Aplica principios SOLID y Clean Code:
    - SRP: Orquesta el flujo entre autenticación, cliente API y persistencia.
    - OCP/DIP: Componentes desacoplados e inyectables.
    - Resiliencia: Reanudación automática (Checkpoints) y tolerancia a fallos.
    """

    def __init__(
        self,
        auth_service: Optional[AuthService] = None,
        persistence: Optional[CsvPersistenceManager] = None,
    ):
        self.auth_service = auth_service or AuthService()
        self.persistence = persistence or CsvPersistenceManager()

    def extract_listado(
        self,
        max_pages: Optional[int] = None,
        page_size: int = 100,
        resume: bool = True,
        headless: bool = True,
    ) -> int:
        """
        Extrae la tabla maestra de postulantes y la almacena en postulantes_listado.csv.
        - Si resume=True, reanuda automáticamente desde el último checkpoint registrado.
        - max_pages: Límite de páginas a extraer (None para descargar todo el sistema).
        - Retorna la cantidad de registros nuevos guardados.
        """
        print("\n" + "=" * 65)
        print("    INICIANDO EXTRACCIÓN DE TABLA MAESTRA (LISTADO POSTULANTES)")
        print("=" * 65)

        # 1. Determinar punto de inicio por checkpoint
        skip = 0
        current_page = 1
        if resume:
            ckpt = self.persistence.load_checkpoint_listado()
            if ckpt and ckpt.last_skip is not None:
                # Si la última página procesada fue N, reanudamos en el siguiente skip
                skip = ckpt.last_skip + ckpt.page_size
                current_page = ckpt.last_page + 1
                logger.info(
                    f"Reanudando desde Checkpoint: Página {current_page} (Skip={skip}) | "
                    f"Ya guardados: {ckpt.total_saved} de {ckpt.total_records}"
                )

        total_saved_in_session = 0

        with self.auth_service.get_authenticated_browser(headless=headless) as (browser, context, page):
            client = SuneduApiClient(context, page)
            if not client.initialize_headers():
                logger.error("No se pudo inicializar el cliente API de SUNEDU.")
                return 0

            pages_processed = 0

            while True:
                if max_pages is not None and pages_processed >= max_pages:
                    logger.info(f"Límite de páginas alcanzado ({max_pages}). Finalizando lote...")
                    break

                logger.info(f"Descargando Página {current_page} (Skip={skip}, PageSize={page_size})...")
                total_records, records = client.fetch_listado_page(skip=skip, page_size=page_size)

                if not records:
                    logger.info("No se recibieron más registros de la API o se llegó al final.")
                    break

                # Guardar en CSV con persistencia atómica y flush
                saved_count = self.persistence.save_listado_batch(
                    records=records,
                    skip=skip,
                    page_num=current_page,
                    total_records=total_records,
                    page_size=page_size,
                )
                total_saved_in_session += saved_count
                pages_processed += 1

                # Calcular avance
                total_pages = (total_records // page_size) + (1 if total_records % page_size > 0 else 0)
                logger.info(
                    f"✔ Progreso: Página {current_page}/{total_pages} procesada | "
                    f"+{saved_count} nuevos registros guardados."
                )

                # Verificar si ya se descargó todo
                if skip + len(records) >= total_records:
                    logger.info("¡Se completó la extracción de todos los registros del sistema!")
                    break

                skip += page_size
                current_page += 1

        print("\n" + "=" * 65)
        print(f"  EXTRACCIÓN DE LISTADO FINALIZADA | Nuevos guardados: {total_saved_in_session}")
        print(f"  Archivo destino: {self.persistence.listado_csv}")
        print("=" * 65)
        return total_saved_in_session

    def extract_detalles(
        self,
        batch_size: int = 50,
        max_records: Optional[int] = None,
        headless: bool = True,
        delay_seconds: float = 0.05,
    ) -> int:
        """
        Lee los postulantes existentes en postulantes_listado.csv que aún no tengan detalle
        y consulta la API de la lupa para guardarlos en postulantes_detalle.csv.
        - Relaciona mediante id_postulante y guid.
        - Guarda en bloques con flush para persistencia inmediata.
        """
        print("\n" + "=" * 65)
        print("    INICIANDO EXTRACCIÓN DE DETALLES PROFUNDOS (MODAL / LUPA)")
        print("=" * 65)

        pending = self.persistence.get_pending_details()
        if not pending:
            logger.info("Todos los postulantes del listado ya tienen sus detalles extraídos.")
            return 0

        total_to_process = min(len(pending), max_records) if max_records else len(pending)
        logger.info(f"Postulantes pendientes de detalle: {len(pending)} (Se procesarán: {total_to_process})")

        total_saved_in_session = 0

        with self.auth_service.get_authenticated_browser(headless=headless) as (browser, context, page):
            client = SuneduApiClient(context, page)
            if not client.initialize_headers():
                logger.error("No se pudo inicializar el cliente API de SUNEDU.")
                return 0

            current_batch: List[PostulanteDetalleRecord] = []
            processed = 0

            for id_postulante, guid, doc_num in pending:
                if max_records and processed >= max_records:
                    break

                detail = client.fetch_detalle(
                    guid=guid,
                    id_postulante=id_postulante,
                    id_persona=0,
                    consultar_colegio=True,
                )
                if detail:
                    current_batch.append(detail)

                processed += 1
                if delay_seconds > 0:
                    time.sleep(delay_seconds)

                # Guardar por bloques
                if len(current_batch) >= batch_size:
                    saved = self.persistence.save_detalle_batch(current_batch)
                    total_saved_in_session += saved
                    logger.info(f"✔ Avance detalles: {processed}/{total_to_process} procesados.")
                    current_batch.clear()

            # Guardar remanente
            if current_batch:
                saved = self.persistence.save_detalle_batch(current_batch)
                total_saved_in_session += saved
                current_batch.clear()

        print("\n" + "=" * 65)
        print(f"  EXTRACCIÓN DE DETALLES FINALIZADA | Nuevos guardados: {total_saved_in_session}")
        print(f"  Archivo destino: {self.persistence.detalle_csv}")
        print("=" * 65)
        return total_saved_in_session
