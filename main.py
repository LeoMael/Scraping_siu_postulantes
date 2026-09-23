#!/usr/bin/env python3
"""
Punto de Entrada: Sistema de Extracción de Postulantes SIU SUNEDU.
Permite ejecutar fácilmente la extracción del listado o de los detalles desde la terminal.
"""

import sys
import argparse
import logging
from postulantes import PostulantesService, CsvPersistenceManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MAIN")


def print_status(persistence: CsvPersistenceManager):
    """Muestra el estado actual de los archivos CSV y checkpoints."""
    print("\n" + "=" * 65)
    print("           ESTADO ACTUAL DE LA EXTRACCIÓN")
    print("=" * 65)

    # 1. Estado del Listado
    saved_listado = persistence.get_saved_listado_ids()
    ckpt_listado = persistence.load_checkpoint_listado()
    print("\n[1] TABLA MAESTRA (postulantes_listado.csv):")
    print(f"  • Registros guardados en CSV: {len(saved_listado)}")
    if ckpt_listado:
        print(f"  • Última página procesada   : {ckpt_listado.last_page}")
        print(f"  • Último Skip               : {ckpt_listado.last_skip}")
        print(f"  • Total en sistema SUNEDU   : {ckpt_listado.total_records}")
        print(f"  • Última actualización      : {ckpt_listado.updated_at}")
    else:
        print("  • Checkpoint: No iniciado")

    # 2. Estado de Detalles
    saved_detalles = persistence.get_saved_detalle_ids()
    pending = persistence.get_pending_details()
    print("\n[2] DETALLES PROFUNDOS (postulantes_detalle.csv):")
    print(f"  • Detalles ya guardados     : {len(saved_detalles)}")
    print(f"  • Pendientes por consultar  : {len(pending)}")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Sistema Modular de Extracción de Postulantes (SIU SUNEDU)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python main.py --status                      # Ver cuántos registros van guardados
  python main.py --listado --paginas 5         # Extraer 5 páginas (500 registros)
  python main.py --listado                     # Extraer todo el sistema (167k) con reanudación
  python main.py --detalles --max 100          # Extraer 100 detalles de la lupa pendientes
  python main.py --listado --headed            # Extraer viendo el navegador en pantalla
        """,
    )
    parser.add_argument("--all", action="store_true", help="Extracción completa: descarga todo el listado y luego todos los detalles")
    parser.add_argument("--listado", action="store_true", help="Extraer la tabla maestra de postulantes")
    parser.add_argument("--detalles", action="store_true", help="Extraer los datos profundos de la lupa/modal")
    parser.add_argument("--status", action="store_true", help="Mostrar resumen de avance actual y salir")
    parser.add_argument("--paginas", type=int, default=None, help="Límite de páginas a extraer (ej. 5). Por defecto: todas hasta el final")
    parser.add_argument("--max", type=int, default=None, help="Límite de registros de detalle a extraer (ej. 100)")
    parser.add_argument("--page-size", type=int, default=100, help="Tamaño de lote por página (por defecto: 100)")
    parser.add_argument("--no-resume", action="store_true", help="Ignorar checkpoint y empezar desde el inicio")
    parser.add_argument("--headed", action="store_true", help="Abrir ventana visible del navegador")

    args = parser.parse_args()

    service = PostulantesService()

    if args.all:
        args.listado = True
        args.detalles = True

    # Si no se pasó ninguna acción o se pasó --status, mostramos el estado
    if args.status or (not args.listado and not args.detalles):
        print_status(service.persistence)
        if not args.listado and not args.detalles:
            print("Comandos disponibles:")
            print("   python run.py --all                   (Extracción completa: listado + detalles)")
            print("   python run.py --listado               (Solo tabla maestra)")
            print("   python run.py --detalles              (Solo detalles de la lupa)")
            print("   python run.py --help                  (Ver todas las opciones)\n")
        return

    is_headless = not args.headed
    resume = not args.no_resume

    # 1. Extraer Listado
    if args.listado:
        service.extract_listado(
            max_pages=args.paginas,
            page_size=args.page_size,
            resume=resume,
            headless=is_headless,
        )

    # 2. Extraer Detalles
    if args.detalles:
        service.extract_detalles(
            batch_size=50,
            max_records=args.max,
            headless=is_headless,
        )

    # Mostrar estado final
    print_status(service.persistence)


if __name__ == "__main__":
    main()
