#!/usr/bin/env python3
"""
Runner Automático de Features - SIU SUNEDU.
Ubicado dentro de features/ pero ejecutable desde cualquier ruta del sistema.
Verifica o inicializa automáticamente su propio entorno virtual (features/venv)
e instala dependencias si faltan, delegando la ejecución a features/main.py.
"""

import sys
import subprocess
from pathlib import Path

# Directorio propio de features/
FEATURES_DIR = Path(__file__).resolve().parent
VENV_DIR = FEATURES_DIR / "venv"
PYTHON_BIN = VENV_DIR / "bin" / "python"
PIP_BIN = VENV_DIR / "bin" / "pip"
MAIN_SCRIPT = FEATURES_DIR / "main.py"
REQUIREMENTS_FILE = FEATURES_DIR / "requirements.txt"


def ensure_environment() -> None:
    """Garantiza que el entorno virtual propio de features esté listo."""
    # 1. Crear venv si no existe
    if not PYTHON_BIN.exists():
        print(f"[AUTO-SETUP] Creando entorno virtual en: {VENV_DIR}...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])

    # 2. Verificar dependencias mínimas
    try:
        subprocess.check_call(
            [str(PYTHON_BIN), "-c", "import playwright; import dotenv"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        print("[AUTO-SETUP] Instalando dependencias requeridas...")
        subprocess.check_call([str(PIP_BIN), "install", "-r", str(REQUIREMENTS_FILE)])
        print("[AUTO-SETUP] Descargando binarios de Chromium para Playwright...")
        subprocess.check_call([str(PYTHON_BIN), "-m", "playwright", "install", "chromium"])
        print("[AUTO-SETUP] Preparación completa.\n")


def main():
    ensure_environment()

    # Ejecutar main.py pasando todos los argumentos
    cmd = [str(PYTHON_BIN), str(MAIN_SCRIPT)] + sys.argv[1:]

    try:
        result = subprocess.run(cmd, cwd=str(FEATURES_DIR))
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n[INFO] Ejecución pausada. El progreso está guardado en los checkpoints.")
        sys.exit(0)


if __name__ == "__main__":
    main()
