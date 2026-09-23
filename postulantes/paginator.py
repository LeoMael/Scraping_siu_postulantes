import re
import math
import logging
from typing import Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .models import PaginationInfo

logger = logging.getLogger(__name__)


class PaginatorController:
    """
    Controlador especializado en la interacción con el componente
    sunedu-data-grid-paginator de Angular Material en SIU SUNEDU.
    """

    SELECTOR_SELECT: str = ".page-size-select mat-select"
    SELECTOR_PANEL_OPTIONS: str = ".mat-select-panel mat-option"
    SELECTOR_PAGE_SIZE_TEXT: str = "sunedu-data-grid-paginator .col-page-size"
    SELECTOR_ACTIVE_PAGE: str = "button.page-number-buttons.active"
    SELECTOR_NEXT_BTN: str = "button[aria-label='next_page'], button:has(mat-icon:has-text('keyboard_arrow_right'))"
    SELECTOR_PREV_BTN: str = "button[aria-label='previous_page'], button:has(mat-icon:has-text('keyboard_arrow_left'))"

    def __init__(self, default_timeout: int = 15000):
        self.default_timeout = default_timeout

    def get_current_page_size(self, page: Page) -> Optional[int]:
        """Obtiene el tamaño de página actualmente seleccionado en el mat-select."""
        try:
            val_element = page.locator(f"{self.SELECTOR_SELECT} .mat-select-value-text").first
            if val_element.count() > 0:
                raw_text = val_element.inner_text().strip()
                if raw_text.isdigit():
                    return int(raw_text)
        except Exception as e:
            logger.debug(f"No se pudo determinar el tamaño actual: {e}")
        return None

    def set_page_size(self, page: Page, size: int = 100) -> bool:
        """
        Cambia el tamaño de página en el paginador de Angular Material (ej. 100).
        Espera a que la tabla se refresque con el nuevo volumen de datos.
        """
        current_size = self.get_current_page_size(page)
        if current_size == size:
            logger.info(f"El paginado ya está configurado en {size} registros.")
            return True

        logger.info(f"Cambiando tamaño de paginado de {current_size} a {size}...")
        try:
            # 1. Clic en el mat-select para abrir las opciones
            select = page.locator(self.SELECTOR_SELECT).first
            select.click(timeout=self.default_timeout)

            # 2. Esperar que el panel desplegable de Angular Material esté visible
            page.wait_for_selector(self.SELECTOR_PANEL_OPTIONS, timeout=self.default_timeout)

            # 3. Localizar y clicar la opción del tamaño deseado
            option = page.locator(self.SELECTOR_PANEL_OPTIONS).filter(has_text=str(size)).first
            if option.count() == 0:
                logger.error(f"La opción '{size}' no está disponible en el paginador.")
                # Cerrar el panel haciendo clic fuera si falló
                page.keyboard.press("Escape")
                return False

            option.click(timeout=self.default_timeout)

            # 4. Esperar a que la tabla cargue el nuevo lote de registros
            # Verificamos que el texto del paginador o las filas se actualicen
            page.wait_for_function(
                f"""() => {{
                    const el = document.querySelector('{self.SELECTOR_SELECT} .mat-select-value-text');
                    return el && el.innerText.trim() === '{size}';
                }}""",
                timeout=self.default_timeout,
            )

            # Pausa de estabilización para el renderizado del DOM de Angular
            page.wait_for_timeout(2000)
            logger.info(f"Paginado actualizado exitosamente a {size} registros por página.")
            return True

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout al cambiar tamaño de paginado a {size}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al cambiar tamaño de paginado: {e}")
            return False

    def get_pagination_info(self, page: Page) -> Optional[PaginationInfo]:
        """
        Lee y estructura los metadatos de paginación de la vista actual.
        Ejemplo: 'Visualizar 100 registros - 1 a 100 de 167872 registros'
        """
        try:
            label_element = page.locator(self.SELECTOR_PAGE_SIZE_TEXT).first
            if label_element.count() == 0:
                return None

            text = label_element.inner_text().strip().replace("\n", " ")

            # Parsear: "1 a 100 de 167872 registros"
            match = re.search(r"(\d+)\s+a\s+(\d+)\s+de\s+(\d+)", text)
            if not match:
                logger.warning(f"No se pudo parsear el texto de paginación: '{text}'")
                return None

            start_idx = int(match.group(1))
            end_idx = int(match.group(2))
            total_records = int(match.group(3))
            page_size = (end_idx - start_idx + 1) if end_idx >= start_idx else 100

            # Determinar página activa
            active_btn = page.locator(self.SELECTOR_ACTIVE_PAGE).first
            current_page = 1
            if active_btn.count() > 0:
                btn_txt = active_btn.inner_text().strip()
                if btn_txt.isdigit():
                    current_page = int(btn_txt)
            else:
                current_page = math.ceil(end_idx / page_size) if page_size > 0 else 1

            total_pages = math.ceil(total_records / page_size) if page_size > 0 else 1

            # Botones de navegación
            next_btn = page.locator(self.SELECTOR_NEXT_BTN).first
            prev_btn = page.locator(self.SELECTOR_PREV_BTN).first

            has_next = (
                next_btn.count() > 0
                and "disabled" not in (next_btn.get_attribute("class") or "")
                and not next_btn.is_disabled()
            )
            has_prev = (
                prev_btn.count() > 0
                and "disabled" not in (prev_btn.get_attribute("class") or "")
                and not prev_btn.is_disabled()
            )

            return PaginationInfo(
                page_size=page_size,
                current_page=current_page,
                start_index=start_idx,
                end_index=end_idx,
                total_records=total_records,
                total_pages=total_pages,
                has_next=has_next,
                has_previous=has_prev,
            )

        except Exception as e:
            logger.warning(f"Error extrayendo información de paginación: {e}")
            return None

    def next_page(self, page: Page) -> bool:
        """Avanza a la siguiente página de registros."""
        info_before = self.get_pagination_info(page)
        if info_before and not info_before.has_next:
            logger.info("No hay más páginas siguientes.")
            return False

        try:
            next_btn = page.locator(self.SELECTOR_NEXT_BTN).first
            if next_btn.count() == 0 or next_btn.is_disabled():
                return False

            next_btn.click(timeout=self.default_timeout)

            # Esperar a que cambie el start_index en el paginador
            if info_before:
                page.wait_for_function(
                    f"""() => {{
                        const el = document.querySelector('{self.SELECTOR_PAGE_SIZE_TEXT}');
                        return el && !el.innerText.includes('{info_before.start_index} a {info_before.end_index}');
                    }}""",
                    timeout=self.default_timeout,
                )
            page.wait_for_timeout(1500)
            return True

        except Exception as e:
            logger.error(f"Error al avanzar a la siguiente página: {e}")
            return False
