import time
import logging
from typing import Optional
from playwright.sync_api import Page

from .config import AuthConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


class PunkuAuthenticator:
    """
    Gestiona la interacción con el formulario de autenticación de SUNEDU PUNKU
    (auth1.sunedu.gob.pe), la resolución del reCAPTCHA v2 invisible y el retorno al SIU.
    """

    def __init__(self, config: AuthConfig = DEFAULT_CONFIG):
        self.config = config

    def complete_form(
        self,
        page: Page,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        """
        Rellena usuario y contraseña en PUNKU, presiona ingresar, espera la resolución
        del captcha invisible de Google y confirma el aterrizaje en el dashboard del SIU.
        """
        user = username or self.config.username
        pwd = password or self.config.password

        logger.info("Esperando campos de entrada en PUNKU (#txtUsername, #txtPassword)...")
        try:
            page.wait_for_selector(self.config.selector_punku_user, timeout=20000)
            page.wait_for_selector(self.config.selector_punku_pass, timeout=20000)
        except Exception as e:
            logger.error(f"No se encontraron los inputs de login en PUNKU: {e}")
            return False

        # Cerrar modal informativo si aparece
        try:
            modal_btn = page.locator(self.config.selector_punku_modal).first
            if modal_btn.is_visible(timeout=1500):
                logger.info("Cerrando modal informativo...")
                modal_btn.click()
                time.sleep(0.3)
        except Exception:
            pass

        if not user or not pwd:
            logger.warning("Credenciales no configuradas. Ingrésalas en el navegador si está visible.")
        else:
            logger.info(f"Escribiendo usuario: '{user}'...")
            txt_user = page.locator(self.config.selector_punku_user)
            txt_user.click()
            txt_user.fill("")
            txt_user.type(user, delay=25)

            time.sleep(0.2)
            logger.info("Escribiendo contraseña...")
            txt_pass = page.locator(self.config.selector_punku_pass)
            txt_pass.click()
            txt_pass.fill("")
            txt_pass.type(pwd, delay=25)

            time.sleep(0.3)
            logger.info("Haciendo clic en el botón de acceso (#btnLoginPunku)...")
            btn_login = page.locator(self.config.selector_punku_btn).first
            btn_login.click()

        logger.info("Esperando resolución de reCAPTCHA invisible y redirección a SIU...")
        try:
            page.wait_for_url(
                lambda u: "auth1" not in u and "siu.sunedu.gob.pe" in u,
                timeout=60000,
            )
            logger.info(f"¡Redirección capturada! URL: {page.url}")
        except Exception as e:
            logger.warning(f"Aviso en espera de redirección: {e}. URL actual: {page.url}")

        logger.info("Esperando confirmación del dashboard SIU (.app-title)...")
        try:
            header_el = page.wait_for_selector(
                self.config.selector_dashboard_header,
                timeout=30000,
            )
            if header_el:
                logger.info(f"¡Autenticación exitosa confirmada! '{header_el.inner_text().strip()}'")
            page.wait_for_timeout(2500)
            return True
        except Exception as e:
            logger.error(f"No se detectó el encabezado en el tiempo esperado: {e}")
            if "logging-in" in page.url:
                logger.info("Aún en /logging-in; esperando 5 segundos adicionales...")
                page.wait_for_timeout(5000)
                if page.locator(self.config.selector_dashboard_header).count() > 0:
                    logger.info("¡Sesión confirmada tras espera adicional!")
                    return True
            return False

    def perform_login(
        self,
        page: Page,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        """
        Ejecuta el flujo de login optimizado:
        - Si ya está en PUNKU (por redirección): inyecta directo.
        - Si está en SIU: busca y clica 'Accede Ahora' sin recargar.
        - Si está en otra URL: navega a SIU_BASE_URL.
        """
        current_url = page.url.lower()

        # CASO 1: Ya estamos en PUNKU
        if self.config.auth_keyword in current_url or page.locator(self.config.selector_punku_user).count() > 0:
            logger.info("El navegador ya se encuentra en PUNKU. Inyectando credenciales directamente...")
            return self.complete_form(page, username, password)

        # CASO 2: Navegar si no estamos en SIU
        if "siu.sunedu.gob.pe" not in current_url:
            logger.info(f"Navegando a la portada: {self.config.base_url}")
            page.goto(self.config.base_url, timeout=self.config.navigation_timeout, wait_until="domcontentloaded")

        # Si la navegación a SIU redirigió en automático a PUNKU (sesión invalidada externamente)
        if self.config.auth_keyword in page.url.lower():
            logger.info("Redirección automática inmediata a PUNKU detectada. Inyectando credenciales...")
            return self.complete_form(page, username, password)

        # CASO 3: Portada pública de SIU -> Clic directo en 'Accede Ahora' sin recargas
        logger.info("Buscando botón 'Accede Ahora' en la portada de SIU...")
        try:
            btn_acceder = page.wait_for_selector(
                self.config.selector_acceder_btn,
                timeout=15000,
            )
            if btn_acceder:
                logger.info(f"Botón detectado ('{btn_acceder.inner_text().strip()}'). Clicando para ir a PUNKU...")
                btn_acceder.click()
        except Exception as e:
            logger.warning(f"Aviso al buscar o pulsar botón de acceso: {e}")

        return self.complete_form(page, username, password)
