#!/usr/bin/env python3
"""
Punto de Entrada: Sistema de Extracción de Postulantes SIU SUNEDU.
Permite ejecutar fácilmente la extracción del listado o de los detalles desde la terminal.
"""

import sys
import argparse
import logging
from postulantes import PostulantesService, CsvPersistenceManager
from carga_masiva import CargaMasivaService, CargaMasivaPersistenceManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MAIN")


def print_status(persistence_postulantes: CsvPersistenceManager, persistence_cargas: CargaMasivaPersistenceManager):
    """Muestra el estado actual de los archivos CSV y checkpoints."""
    print("\n" + "=" * 65)
    print("           ESTADO ACTUAL DE LA EXTRACCIÓN (SIU SUNEDU)")
    print("=" * 65)

    # 1. Estado del Listado
    saved_listado = persistence_postulantes.get_saved_listado_ids()
    ckpt_listado = persistence_postulantes.load_checkpoint_listado()
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
    saved_detalles = persistence_postulantes.get_saved_detalle_ids()
    pending = persistence_postulantes.get_pending_details()
    print("\n[2] DETALLES PROFUNDOS (postulantes_detalle.csv):")
    print(f"  • Detalles ya guardados     : {len(saved_detalles)}")
    print(f"  • Pendientes por consultar  : {len(pending)}")

    # 3. Estado de Cargas Masivas
    saved_cargas = persistence_cargas.get_saved_ids()
    print("\n[3] CARGAS MASIVAS (cargas_masivas_consolidado.csv):")
    print(f"  • Registros acumulados (>=2021): {len(saved_cargas)}")
    if persistence_cargas.base_dir.exists():
        subdirs = [d for d in persistence_cargas.base_dir.iterdir() if d.is_dir() and (d / "historial_cargas.csv").exists()]
        for sd in subdirs:
            csv_path = sd / "historial_cargas.csv"
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                lines = max(0, sum(1 for _ in f) - 1)
            print(f"    - {sd.name}: {lines} registros")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Sistema Modular de Extracción (SIU SUNEDU)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python main.py --status                      # Ver cuántos registros van guardados
  python main.py --listado --paginas 5         # Extraer 5 páginas de postulantes
  python main.py --cargas                      # Extraer historial de Cargas Masivas (desde 2021)
  python main.py --detalles --max 100          # Extraer 100 detalles de la lupa pendientes
        """,
    )
    parser.add_argument("--all", action="store_true", help="Extracción completa de postulantes (listado + detalles)")
    parser.add_argument("--listado", action="store_true", help="Extraer la tabla maestra de postulantes")
    parser.add_argument("--detalles", action="store_true", help="Extraer los datos profundos de la lupa/modal")
    parser.add_argument("--cargas", action="store_true", help="Extraer y clasificar historial de Cargas Masivas (desde 2021)")
    parser.add_argument("--descargar-excels", "--excels", dest="descargar_excels", action="store_true", help="Descargar archivos Excel físicos (originales, válidos y observados)")
    parser.add_argument("--tipo", type=str, default=None, help="Filtrar por tipo de carga (ej. 'postulantes', 'matricula', '26', '2')")
    parser.add_argument("--tipo-id", type=int, default=None, help="Filtrar directamente por idTblTipoCarga numérico (ej. 26 postulantes, 2 matricula)")
    parser.add_argument("--todas-fechas", action="store_true", help="Ignorar filtro de fecha y traer todo el histórico disponible")
    parser.add_argument("--solo-observados", action="store_true", help="Descargar únicamente archivos de registros observados")
    parser.add_argument("--solo-validos", action="store_true", help="Descargar únicamente archivos de registros válidos")
    parser.add_argument("--solo-originales", action="store_true", help="Descargar únicamente archivos originales subidos")
    parser.add_argument("--status", action="store_true", help="Mostrar resumen de avance actual y salir")
    parser.add_argument("--fecha-desde", type=str, default="2021-01-01T00:00:00-05:00", help="Fecha base para cargas masivas (por defecto: 2021-01-01)")
    parser.add_argument("--paginas", type=int, default=None, help="Límite de páginas a extraer")
    parser.add_argument("--max", type=int, default=None, help="Límite de registros a extraer")
    parser.add_argument("--page-size", type=int, default=100, help="Tamaño de lote por página (por defecto: 100)")
    parser.add_argument("--no-resume", action="store_true", help="Ignorar checkpoint y empezar desde el inicio")
    parser.add_argument("--headed", action="store_true", help="Abrir ventana visible del navegador")

    args = parser.parse_args()

    service_postulantes = PostulantesService()
    service_cargas = CargaMasivaService()

    if args.all:
        args.listado = True
        args.detalles = True

    # Si no se pasó ninguna acción o se pasó --status, mostramos el estado
    if args.status or (not args.listado and not args.detalles and not args.cargas and not args.descargar_excels):
        print_status(service_postulantes.persistence, service_cargas.persistence)
        if not args.listado and not args.detalles and not args.cargas and not args.descargar_excels:
            print("Comandos disponibles:")
            print("   python run.py --cargas                (Descargar historial de Cargas Masivas)")
            print("   python run.py --descargar-excels      (Descargar los Excels: originales, válidos y observados)")
            print("   python run.py --all                   (Extracción completa postulantes: listado + detalles)")
            print("   python run.py --listado               (Solo tabla maestra postulantes)")
            print("   python run.py --detalles              (Solo detalles de la lupa)")
            print("   python run.py --help                  (Ver todas las opciones)\n")
        return

    is_headless = not args.headed
    resume = not args.no_resume

    # 1. Extraer Listado de Postulantes
    if args.listado:
        service_postulantes.extract_listado(
            max_pages=args.paginas,
            page_size=args.page_size,
            resume=resume,
            headless=is_headless,
        )

    # 2. Extraer Detalles de Postulantes
    if args.detalles:
        service_postulantes.extract_detalles(
            batch_size=50,
            max_records=args.max,
            headless=is_headless,
        )

    # 3. Extraer Historial de Cargas Masivas
    if args.cargas:
        fecha_filtro = None if args.todas_fechas else args.fecha_desde
        service_cargas.sync_historial(
            tipo_carga=args.tipo,
            id_tipo_carga=args.tipo_id,
            fecha_desde=fecha_filtro,
            page_size=args.page_size,
            resume=resume,
            headless=is_headless,
        )

    # 4. Descargar Archivos Excel Físicos (Originales, Válidos, Observados)
    if args.descargar_excels:
        desc_orig = not (args.solo_validos or args.solo_observados) or args.solo_originales
        desc_val = not (args.solo_originales or args.solo_observados) or args.solo_validos
        desc_obs = not (args.solo_originales or args.solo_validos) or args.solo_observados

        service_cargas.download_excels(
            tipo_carga=args.tipo,
            descargar_original=desc_orig,
            descargar_validos=desc_val,
            descargar_observados=desc_obs,
            max_cargas=args.max,
            headless=is_headless,
        )

    # Mostrar estado final
    print_status(service_postulantes.persistence, service_cargas.persistence)


if __name__ == "__main__":
    main()
