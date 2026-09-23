import os
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Set, List, Optional, Tuple, Dict, Any

from .models import (
    PostulanteListadoRecord,
    PostulanteDetalleRecord,
    CheckpointListado,
    CheckpointDetalle,
)

logger = logging.getLogger(__name__)


class CsvPersistenceManager:
    """
    Gestor de persistencia en CSV con tolerancia a fallos, prevención de duplicados
    y reanudación automática (Checkpoints).
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            # Por defecto: features/data/
            features_dir = Path(__file__).resolve().parent.parent
            self.data_dir = features_dir / "data"
        else:
            self.data_dir = Path(data_dir)

        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.listado_csv = self.data_dir / "postulantes_listado.csv"
        self.detalle_csv = self.data_dir / "postulantes_detalle.csv"
        self.checkpoint_listado_file = self.data_dir / "checkpoint_listado.json"
        self.checkpoint_detalle_file = self.data_dir / "checkpoint_detalle.json"

    # ==========================================
    # GESTIÓN DE TABLA MAESTRA (LISTADO)
    # ==========================================

    def get_saved_listado_ids(self) -> Set[int]:
        """Obtiene el conjunto de id_postulante ya almacenados en postulantes_listado.csv."""
        if not self.listado_csv.exists() or self.listado_csv.stat().st_size == 0:
            return set()
        saved_ids: Set[int] = set()
        try:
            with open(self.listado_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_id = row.get("id_postulante")
                    if raw_id and raw_id.isdigit():
                        saved_ids.add(int(raw_id))
        except Exception as e:
            logger.warning(f"Error leyendo IDs existentes de listado ({e}).")
        return saved_ids

    def load_checkpoint_listado(self) -> Optional[CheckpointListado]:
        """Carga el último estado guardado de la extracción del listado."""
        if not self.checkpoint_listado_file.exists():
            return None
        try:
            with open(self.checkpoint_listado_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CheckpointListado(
                last_skip=data["last_skip"],
                last_page=data["last_page"],
                page_size=data["page_size"],
                total_records=data["total_records"],
                total_saved=data["total_saved"],
                last_id_postulante=data.get("last_id_postulante"),
                updated_at=data["updated_at"],
            )
        except Exception as e:
            logger.warning(f"Checkpoint de listado inválido o corrupto ({e}).")
            return None

    def save_listado_batch(
        self,
        records: List[PostulanteListadoRecord],
        skip: int,
        page_num: int,
        total_records: int,
        page_size: int = 100,
    ) -> int:
        """
        Agrega un lote de registros a postulantes_listado.csv y actualiza el checkpoint.
        Retorna la cantidad de registros nuevos efectivamente guardados.
        """
        if not records:
            return 0

        saved_ids = self.get_saved_listado_ids()
        new_records = [r for r in records if r.id_postulante not in saved_ids]

        if not new_records:
            logger.info("Todos los registros del lote ya estaban presentes en el CSV. Omitiendo duplicados.")
            return 0

        file_exists = self.listado_csv.exists() and self.listado_csv.stat().st_size > 0
        fieldnames = list(new_records[0].to_dict().keys())

        with open(self.listado_csv, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            for rec in new_records:
                writer.writerow(rec.to_dict())
            f.flush()
            os.fsync(f.fileno())

        # Actualizar checkpoint
        total_saved = len(saved_ids) + len(new_records)
        last_id = new_records[-1].id_postulante if new_records else None
        checkpoint_data = {
            "last_skip": skip,
            "last_page": page_num,
            "page_size": page_size,
            "total_records": total_records,
            "total_saved": total_saved,
            "last_id_postulante": last_id,
            "updated_at": datetime.now().isoformat(),
        }
        self._write_json_atomic(self.checkpoint_listado_file, checkpoint_data)
        logger.info(f"Guardados {len(new_records)} registros en {self.listado_csv.name} (Total acumulado: {total_saved})")
        return len(new_records)

    # ==========================================
    # GESTIÓN DE DETALLES (LUPA / MODAL)
    # ==========================================

    def get_saved_detalle_ids(self) -> Set[int]:
        """Obtiene el conjunto de id_postulante ya detallados en postulantes_detalle.csv."""
        if not self.detalle_csv.exists() or self.detalle_csv.stat().st_size == 0:
            return set()
        saved_ids: Set[int] = set()
        try:
            with open(self.detalle_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_id = row.get("id_postulante")
                    if raw_id and raw_id.isdigit():
                        saved_ids.add(int(raw_id))
        except Exception as e:
            logger.warning(f"Error leyendo IDs existentes de detalle ({e}).")
        return saved_ids

    def save_detalle_batch(self, records: List[PostulanteDetalleRecord]) -> int:
        """
        Agrega un lote de registros detallados a postulantes_detalle.csv y actualiza el checkpoint.
        """
        if not records:
            return 0

        saved_ids = self.get_saved_detalle_ids()
        new_records = [r for r in records if r.id_postulante not in saved_ids]

        if not new_records:
            return 0

        file_exists = self.detalle_csv.exists() and self.detalle_csv.stat().st_size > 0
        fieldnames = list(new_records[0].to_dict().keys())

        with open(self.detalle_csv, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            for rec in new_records:
                writer.writerow(rec.to_dict())
            f.flush()
            os.fsync(f.fileno())

        total_saved = len(saved_ids) + len(new_records)
        checkpoint_data = {
            "total_saved": total_saved,
            "last_id_postulante": new_records[-1].id_postulante if new_records else None,
            "updated_at": datetime.now().isoformat(),
        }
        self._write_json_atomic(self.checkpoint_detalle_file, checkpoint_data)
        logger.info(f"Guardados {len(new_records)} detalles en {self.detalle_csv.name} (Total acumulado: {total_saved})")
        return len(new_records)

    def get_pending_details(self) -> List[Tuple[int, str, str]]:
        """
        Compara postulantes_listado.csv con postulantes_detalle.csv para retornar
        la lista de tuplas (id_postulante, guid, documento_numero) pendientes de detalle.
        """
        if not self.listado_csv.exists():
            return []

        saved_details = self.get_saved_detalle_ids()
        pending: List[Tuple[int, str, str]] = []

        with open(self.listado_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id = row.get("id_postulante", "")
                guid = row.get("guid", "")
                raw_doc = row.get("documento_identidad", "")
                if raw_id and raw_id.isdigit():
                    postulante_id = int(raw_id)
                    if postulante_id not in saved_details and guid:
                        # Extraer solo número del documento
                        doc_num = raw_doc.split()[-1] if raw_doc else ""
                        pending.append((postulante_id, guid, doc_num))
        return pending

    # ==========================================
    # UTILITARIOS INTERNOS
    # ==========================================

    @staticmethod
    def _write_json_atomic(target_path: Path, data: Dict[str, Any]) -> None:
        """Escribe un archivo JSON de forma atómica para evitar corrupción ante fallos."""
        temp_path = target_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            temp_path.replace(target_path)
        except Exception as e:
            logger.error(f"Error escribiendo archivo atómico '{target_path}': {e}")
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
