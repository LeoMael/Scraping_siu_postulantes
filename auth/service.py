import sys
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Generator
from playwright.sync_api import Playwright, Browser, BrowserContext, Page, sync_playwright

from .config import AuthConfig, DEFAULT_CONFIG
from .storage import SessionStorage
from .authenticator import PunkuAuthenticator

logger = logging.getLogger(__name__)


class AuthService:
    """
    Feature de Autenticación: Login y Relogin en SUNEDU SIU / PUNKU.
    
    Responsabilidades:
    1. Validar sesión existente (reutilización en ~3-4 segundos).
    2. Manejar relogin automático ante expiración o invalidación externa (en otra máquina).
    3. Cero recargas de página redundantes (inyección directa en la misma pestaña).
    4. Guardado atómico seguro para evitar corrupción del archivo JSON.
    5. Provisión limpia de credenciales (cookies, tokens JWT/localStorage) o contexto del navegador.
    """

    def __init__(
        self,
        config: AuthConfig = DEFAULT_CONFIG,
        storage: Optional[SessionStorage] = None,
        authenticator: Optional[PunkuAuthenticator] = None,
    ):
        self.config = config
        self.storage = storage or SessionStorage(config.session_file)
        self.authenticator = authenticator or PunkuAuthenticator(config)

    def _apply_stealth(self, context: BrowserContext) -> None:
        """Inyecta scripts para eliminar huellas de automatización en Chromium."""
        platform = "Win32" if sys.platform == "win32" else "Linux x86_64"
        context.add_init_script(f"""
            Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
            Object.defineProperty(navigator, 'platform', {{ get: () => '{platform}' }});
            Object.defineProperty(navigator, 'plugins', {{ get: () => [1, 2, 3, 4, 5] }});
            Object.defineProperty(navigator, 'languages', {{ get: () => ['es-419', 'es', 'en-US', 'en'] }});
            window.chrome = {{ runtime: {{}} }};
        """)

    def create_browser_context(
        self,
        playwright: Playwright,
        headless: Optional[bool] = None,
        storage_state: Optional[Path] = None,
    ) -> Tuple[Browser, BrowserContext]:
        """Inicia el navegador aplicando stealth y cargando sesión validada."""
        is_headless = self.config.headless if headless is None else headless
        launch_kwargs = {
            "headless": is_headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--start-maximized",
            ],
        }

        if self.config.browser_channel:
            try:
                launch_kwargs["channel"] = self.config.browser_channel
                browser = playwright.chromium.launch(**launch_kwargs)
            except Exception as e:
                logger.warning(f"No se pudo usar canal '{self.config.browser_channel}' ({e}). Usando Chromium...")
                launch_kwargs.pop("channel", None)
                browser = playwright.chromium.launch(**launch_kwargs)
        else:
            browser = playwright.chromium.launch(**launch_kwargs)

        if sys.platform == "win32":
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
        else:
            user_agent = (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )

        context_kwargs = {
            "viewport": {"width": 1366, "height": 768},
            "user_agent": user_agent,
            "locale": "es-419",
            "timezone_id": "America/Lima",
        }

        # Solo inyectar si el archivo es un JSON válido
        if storage_state and self.storage.is_valid(storage_state):
            logger.info(f"Cargando sesión previa desde: {storage_state}")
            context_kwargs["storage_state"] = str(storage_state)

        try:
            context = browser.new_context(**context_kwargs)
        except Exception as e:
            logger.warning(f"Fallo al abrir contexto con sesión ({e}). Abriendo contexto limpio...")
            context_kwargs.pop("storage_state", None)
            if storage_state:
                self.storage.clear(storage_state)
            context = browser.new_context(**context_kwargs)

        self._apply_stealth(context)
        return browser, context

    def get_authenticated_context(
        self,
        playwright: Playwright,
        headless: Optional[bool] = None,
        force_login: bool = False,
    ) -> Tuple[Browser, BrowserContext, Page]:
        """
        Orquesta el ciclo de Login y Relogin en una única ventana:
        - Abre UNA SOLA ventana de navegador.
        - Si la sesión sigue viva: entra en ~3s sin pedir credenciales.
        - Si SUNEDU redirigió directo a PUNKU (sesión invalidada en otro lado): inyecta directo en esa pestaña.
        - Si la sesión expiró (botón 'Accede Ahora'): clica en esa misma pestaña sin recargar.
        - Guarda la sesión de forma atómica y segura si se renovó.
        """
        session_path = self.config.session_file
        has_saved_session = not force_login and self.storage.is_valid(session_path)

        browser, context = self.create_browser_context(
            playwright,
            headless=headless,
            storage_state=session_path if has_saved_session else None,
        )
        page = context.new_page()

        if has_saved_session:
            logger.info(f"Comprobando validez de sesión en: {self.config.base_url}")
            try:
                page.goto(self.config.base_url, timeout=self.config.default_timeout, wait_until="domcontentloaded")
            except Exception as e:
                logger.warning(f"Error cargando URL inicial: {e}")

            # Evaluar rápidamente el estado del portal
            logger.info("Detectando estado de la sesión...")
            try:
                detected = page.wait_for_selector(self.config.selector_combined_state, timeout=12000)
            except Exception:
                detected = None

            current_url = page.url.lower()

            # CASO 1: Redirección automática a PUNKU (sesión invalidada en otro dispositivo)
            if self.config.auth_keyword in current_url or (detected and detected.evaluate("el => el.id === 'txtUsername'")):
                logger.info("Detectada redirección directa a PUNKU (sesión invalidada externamente en otro lado).")
                logger.info("¡Inyectando credenciales de inmediato en la misma pestaña sin perder tiempo!")
                success = self.authenticator.complete_form(page)
                if success:
                    self.storage.save_atomic(context, session_path)
                return browser, context, page

            # CASO 2: Sesión activa confirmada (apareció .app-title o .app-version)
            if detected:
                tag_or_class = detected.evaluate("el => (el.className || '') + ' ' + (el.tagName || '')").lower()
                if "btn-orange" not in tag_or_class and "txtusername" not in tag_or_class:
                    logger.info(f"¡Sesión activa confirmada en SIU! Header: '{detected.inner_text().strip()}'")
                    logger.info("Reutilizando sesión existente sin necesidad de login.")
                    return browser, context, page

            # CASO 3: Sesión expirada -> Clic en 'Accede Ahora' en la MISMA pestaña sin recargar
            logger.info("Sesión expirada (apareció 'Accede Ahora'). Clicando en la MISMA ventana sin recargar...")
            try:
                btn_orange = page.locator(self.config.selector_acceder_btn).first
                btn_orange.click()
            except Exception as e:
                logger.warning(f"Aviso al pulsar 'Accede Ahora': {e}")

            success = self.authenticator.complete_form(page)
            if success:
                self.storage.save_atomic(context, session_path)
            return browser, context, page

        # CASO 4: No había sesión previa guardada o se forzó login
        logger.info("No hay sesión guardada previa o se forzó login. Iniciando flujo de acceso...")
        success = self.authenticator.perform_login(page)
        if success:
            self.storage.save_atomic(context, session_path)
        else:
            logger.warning("No se pudo confirmar el inicio de sesión.")

        return browser, context, page

    def get_credentials(self, headless: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Obtiene los datos de credenciales activos (cookies, tokens JWT/localStorage).
        Si la sesión expiró o no existe, ejecuta el login/relogin y retorna las credenciales frescas.
        Ideal para que cualquier script de scraping consuma la sesión directamente.
        """
        session_path = self.config.session_file
        if force_refresh or not self.storage.is_valid(session_path):
            logger.info("Sesión no disponible o refresco forzado. Autenticando para extraer credenciales...")
            with sync_playwright() as playwright:
                browser, context, page = self.get_authenticated_context(
                    playwright,
                    headless=headless,
                    force_login=force_refresh,
                )
                context.close()
                browser.close()

        return self.storage.extract_credentials(session_path)

    @contextmanager
    def get_authenticated_browser(
        self,
        headless: Optional[bool] = None,
        force_login: bool = False,
    ) -> Generator[Tuple[Browser, BrowserContext, Page], None, None]:
        """
        Context manager que entrega un navegador listo y autenticado en el SIU.
        Al salir del bloque 'with', cierra el contexto y el navegador automáticamente.
        """
        with sync_playwright() as playwright:
            browser, context, page = self.get_authenticated_context(
                playwright,
                headless=headless,
                force_login=force_login,
            )
            try:
                yield browser, context, page
            finally:
                context.close()
                browser.close()
