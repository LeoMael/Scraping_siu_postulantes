import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.sync_api import BrowserContext

logger = logging.getLogger(__name__)


class SessionStorage:
    """
    Gestor de almacenamiento de sesión con persistencia atómica y validación estricta.
    Previene errores de JSON corrupto o truncado ('Extra data').
    """

    def __init__(self, default_path: Path):
        self.default_path = default_path

    def is_valid(self, path: Optional[Path] = None) -> bool:
        """Comprueba si el archivo existe y contiene JSON válido con estructura de sesión."""
        target = path or self.default_path
        if not target or not target.exists() or target.stat().st_size == 0:
            return False
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            return isinstance(data, dict) and ("cookies" in data or "origins" in data)
        except Exception as e:
            logger.warning(f"Sesión dañada o residual en '{target}' ({e}). Descartando archivo...")
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass
            return False

    def load_data(self, path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """Carga el contenido crudo del archivo de sesión."""
        target = path or self.default_path
        if not self.is_valid(target):
            return None
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def extract_credentials(self, path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Extrae de forma limpia y estructurada los tokens y cookies de la sesión:
        - cookies: lista de dicts de cookies (incluyendo cookies de sesión)
        - tokens: valores de 'siu.session', 'punku.code', etc. extraídos de localStorage
        - storage_file: ruta absoluta al archivo para reutilización directa en Playwright
        """
        target = path or self.default_path
        raw_data = self.load_data(target)
        if not raw_data:
            return {"cookies": [], "tokens": {}, "storage_file": str(target)}

        cookies = raw_data.get("cookies", [])
        tokens: Dict[str, str] = {}

        # Extraer localStorage de orígenes (https://siu.sunedu.gob.pe)
        for origin in raw_data.get("origins", []):
            if "siu.sunedu.gob.pe" in origin.get("origin", ""):
                for item in origin.get("localStorage", []):
                    name = item.get("name")
                    val = item.get("value", "")
                    # Limpiar comillas extras si vienen escapadas en JSON
                    if val.startswith('"') and val.endswith('"'):
                        val = val[1:-1]
                    tokens[name] = val

        return {
            "cookies": cookies,
            "tokens": tokens,
            "storage_file": str(target),
        }

    def save_atomic(self, context: BrowserContext, path: Optional[Path] = None) -> bool:
        """
        Escribe el estado de sesión de forma atómica y segura para evitar
        corrupción o bytes residuales ('Extra data').
        """
        target = path or self.default_path
        try:
            temp_path = target.with_suffix(".tmp")
            state = context.storage_state()
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            temp_path.replace(target)
            logger.info(f"Sesión guardada exitosamente de forma atómica en: {target}")
            return True
        except Exception as e:
            logger.warning(f"Aviso en guardado atómico ({e}), usando guardado estándar...")
            try:
                context.storage_state(path=str(target))
                return True
            except Exception as e2:
                logger.error(f"Error crítico al guardar sesión: {e2}")
                return False

    def clear(self, path: Optional[Path] = None) -> None:
        """Elimina el archivo de sesión almacenado."""
        target = path or self.default_path
        try:
            target.unlink(missing_ok=True)
            logger.info(f"Archivo de sesión eliminado: {target}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar el archivo de sesión: {e}")
