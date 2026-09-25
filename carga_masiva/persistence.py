import os
import csv
import json
import re
import logging
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Dict, Any

from .models import CargaMasivaRecord

logger = logging.getLogger(__name__)


def slugify_tipo(text: str) -> str:
    """Convierte un nombre de tipo de carga en una carpeta limpia (ej: 'Datos de matrícula' -> 'datos_de_matricula')."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text.lower()).strip()
    return re.sub(r'[-\s]+', '_', text)


class CargaMasivaPersistenceManager:
    """
    Gestor de persistencia en CSV estructurado y dividido por tipo de carga.
    Crea subcarpetas específicas para cada tipo (postulante, matrícula, ingreso, egresado, etc.)
    y un archivo consolidado general.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            features_dir = Path(__file__).resolve().parent.parent
            self.base_dir = features_dir / "data" / "cargas_masivas"
        else:
            self.base_dir = Path(data_dir)

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.consolidado_csv = self.base_dir / "cargas_masivas_consolidado.csv"
        self.checkpoint_file = self.base_dir / "checkpoint_cargas.json"

    def get_dirs_for_tipo(self, tipo_carga: str) -> Dict[str, Path]:
        """
        Retorna las rutas a las 3 subcarpetas organizadas para un tipo de carga:
        - originales/: archivo Excel que se subió inicialmente
        - validos/: archivo Excel de registros válidos
        - observados/: archivo Excel de observaciones / errores
        """
        folder_name = slugify_tipo(tipo_carga) or "otros"
        target_dir = self.base_dir / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        orig_dir = target_dir / "originales"
        val_dir = target_dir / "validos"
        obs_dir = target_dir / "observados"

        orig_dir.mkdir(parents=True, exist_ok=True)
        val_dir.mkdir(parents=True, exist_ok=True)
        obs_dir.mkdir(parents=True, exist_ok=True)

        return {
            "root": target_dir,
            "originales": orig_dir,
            "validos": val_dir,
            "observados": obs_dir,
        }

    def get_dir_for_tipo(self, tipo_carga: str) -> Path:
        """Retorna la carpeta raíz correspondiente a un tipo de carga específico."""
        return self.get_dirs_for_tipo(tipo_carga)["root"]

    def get_csv_for_tipo(self, tipo_carga: str) -> Path:
        """Retorna la ruta al CSV específico para ese tipo de carga."""
        return self.get_dir_for_tipo(tipo_carga) / "historial_cargas.csv"

    def get_checkpoint_file(self, filter_key: Optional[str] = None) -> Path:
        """Retorna la ruta del checkpoint correspondiente al filtro activo."""
        if filter_key:
            clean_key = re.sub(r'[^\w-]', '_', str(filter_key).lower())
            return self.base_dir / f"checkpoint_cargas_{clean_key}.json"
        return self.checkpoint_file

    def get_cargas_from_csv(self, tipo_carga: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lee los registros existentes desde el CSV consolidado o filtrado por tipo/ID."""
        if not self.consolidado_csv.exists():
            return []

        records = []
        with open(self.consolidado_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if not tipo_carga:
                    records.append(r)
                else:
                    val = str(tipo_carga).strip().lower()
                    val_stem = val[:-1] if val.endswith("s") and len(val) > 3 else val
                    row_id = str(r.get("id_tipo_carga", "")).strip().lower()
                    row_tipo = str(r.get("tipo_carga", "")).strip().lower()
                    slug_tipo = slugify_tipo(row_tipo)

                    if (
                        val == row_id
                        or val in row_tipo
                        or val_stem in row_tipo
                        or slugify_tipo(val_stem) in slug_tipo
                        or (val in ("26", "postulante", "postulantes") and "postulante" in row_tipo)
                        or (val in ("2", "matricula", "matriculas", "matrícula") and "matr" in row_tipo)
                    ):
                        records.append(r)
        return records

    def get_saved_ids(self) -> Set[int]:
        """Obtiene el conjunto de id_carga ya guardados en el archivo consolidado."""
        if not self.consolidado_csv.exists() or self.consolidado_csv.stat().st_size == 0:
            return set()
        saved: Set[int] = set()
        try:
            with open(self.consolidado_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_id = row.get("id_carga")
                    if raw_id and raw_id.isdigit():
                        saved.add(int(raw_id))
        except Exception as e:
            logger.warning(f"Error leyendo IDs guardados de cargas masivas ({e}).")
        return saved

    def load_checkpoint(self, filter_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Carga el último estado guardado de la extracción de cargas masivas según el filtro."""
        ckpt_path = self.get_checkpoint_file(filter_key)
        if not ckpt_path.exists():
            return None
        try:
            with open(ckpt_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_batch(
        self,
        records: List[CargaMasivaRecord],
        skip: int,
        page_num: int,
        total_records: int,
        page_size: int = 100,
        filter_key: Optional[str] = None,
    ) -> int:
        """
        Guarda un lote de registros dividiéndolos por tipo de carga y en el archivo consolidado.
        Evita duplicados por id_carga.
        """
        if not records:
            return 0

        saved_ids = self.get_saved_ids()
        new_records = [r for r in records if r.id_carga not in saved_ids]

        if not new_records:
            return 0

        # 1. Guardar en el consolidado general
        self._append_to_csv(self.consolidado_csv, new_records)

        # 2. Guardar dividiendo por tipo de carga
        by_tipo: Dict[str, List[CargaMasivaRecord]] = {}
        for r in new_records:
            by_tipo.setdefault(r.tipo_carga, []).append(r)

        for tipo, group in by_tipo.items():
            tipo_csv = self.get_csv_for_tipo(tipo)
            self._append_to_csv(tipo_csv, group)

        # 3. Actualizar checkpoint atómico
        total_saved = len(saved_ids) + len(new_records)
        checkpoint_data = {
            "last_skip": skip,
            "last_page": page_num,
            "page_size": page_size,
            "total_records": total_records,
            "total_saved": total_saved,
            "last_id_carga": new_records[-1].id_carga if new_records else None,
            "updated_at": datetime.now().isoformat(),
        }
        ckpt_path = self.get_checkpoint_file(filter_key)
        self._write_json_atomic(ckpt_path, checkpoint_data)
        logger.info(f"Guardados {len(new_records)} registros de cargas masivas (Acumulado: {total_saved})")
        return len(new_records)

    def _append_to_csv(self, file_path: Path, records: List[CargaMasivaRecord]) -> None:
        """Escribe una lista de registros en un archivo CSV asegurando cabeceras y sincronización."""
        if not records:
            return
        file_exists = file_path.exists() and file_path.stat().st_size > 0
        fieldnames = list(records[0].to_dict().keys())

        with open(file_path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            for rec in records:
                writer.writerow(rec.to_dict())
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def _write_json_atomic(target_path: Path, data: Dict[str, Any]) -> None:
        """Escribe un archivo JSON de forma atómica para evitar corrupción."""
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
