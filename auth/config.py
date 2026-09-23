from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

# Directorio de features y raíz
FEATURES_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = FEATURES_DIR / ".env" if (FEATURES_DIR / ".env").exists() else FEATURES_DIR.parent / ".env"
load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class AuthConfig:
    """Configuración inmutable para la feature de Login y Relogin en SIU/PUNKU."""
    username: str = os.getenv("SUNEDU_USERNAME", "")
    password: str = os.getenv("SUNEDU_PASSWORD", "")
    base_url: str = os.getenv("SIU_BASE_URL", "https://siu.sunedu.gob.pe")
    auth_keyword: str = "auth1.sunedu.gob.pe"
    session_file: Path = (
        (FEATURES_DIR / os.getenv("SESSION_FILE", "auth_session.json"))
        if (FEATURES_DIR / "auth_session.json").exists()
        else (FEATURES_DIR.parent / os.getenv("SESSION_FILE", "auth_session.json"))
    )
    headless: bool = os.getenv("HEADLESS", "False").lower() in ("true", "1", "yes")
    browser_channel: str = os.getenv("BROWSER_CHANNEL", "chrome")
    default_timeout: int = 30000
    navigation_timeout: int = 60000

    # Selectores de elementos clave
    selector_dashboard_header: str = ".app-title, .app-version, span:has-text('Sistema de Información Universitaria')"
    selector_acceder_btn: str = "button.btn-orange, .btn-orange, button:has-text('Accede Ahora')"
    selector_punku_user: str = "#txtUsername"
    selector_punku_pass: str = "#txtPassword"
    selector_punku_btn: str = "#btnLoginPunku"
    selector_punku_modal: str = "#btnMensajeInformativoAceptar, button:has-text('Aceptar')"

    # Selector de detección combinada de estado (PUNKU vs Dashboard vs Portada)
    selector_combined_state: str = (
        "#txtUsername, .app-title, .app-version, button.btn-orange, .btn-orange"
    )


# Instancia por defecto
DEFAULT_CONFIG = AuthConfig()
