# Guia de Extraccion - SIU SUNEDU

Modulo de extraccion masiva y persistencia para postulantes en SIU SUNEDU.

---

## 1. Ejecucion Rapida y Automatica (Recomendado)

El script `run.py` se encarga de todo automaticamente. Si no existe el entorno virtual o faltan librerias, las instala por si solo sin configuraciones manuales:

```bash
cd features

# Si ejecutas solo "python run.py":
# Te muestra el estado actual de los CSVs y los comandos disponibles.
python run.py
```

---

## 2. EXTRACCION TOTAL (Todo el Sistema)

### Opcion A: Extraccion 100% Completa (Listado + Detalles de la Lupa)
Descarga la tabla maestra completa (167,872 registros) y luego extrae todos los datos profundos del modal (celular, correo, fecha de nacimiento, puntajes, etc.):

```bash
python run.py --all
```

### Opcion B: Extraccion de la Tabla Maestra (Recomendada inicialmente)
Descarga los 167,872 registros de la lista principal en `postulantes_listado.csv` de forma ultra rapida (~1 segundo por cada 100 registros):

```bash
python run.py --listado
```

### Opcion C: Extraccion de Detalles de la Lupa
Consulta los datos profundos del modal para los registros que ya esten en el listado y los guarda en `postulantes_detalle.csv`:

```bash
# Extraer todos los detalles pendientes:
python run.py --detalles

# Extraer un lote especifico (ej. 500 detalles):
python run.py --detalles --max 500
```

> **Tolerancia a fallos:** Todos los comandos cuentan con reanudacion automatica (checkpoints). Si se corta la conexion o cancelas con `Ctrl + C`, al volver a ejecutar continuara exactamente donde se quedo sin duplicar registros.

---

## 3. Consultar Estado del Avance

Muestra la cantidad de registros guardados en los CSVs, la ultima pagina procesada y los pendientes:

```bash
python run.py --status
```

---

## 4. Opciones Adicionales

* **Extraer una cantidad limitada de paginas (ej. 10 paginas = 1000 registros):**
  ```bash
  python run.py --listado --paginas 10
  ```

* **Abrir ventana visible del navegador en tu pantalla:**
  ```bash
  python run.py --listado --paginas 2 --headed
  ```

* **Reiniciar desde cero (ignorar checkpoint anterior):**
  ```bash
  python run.py --listado --no-resume
  ```

---

## 5. Instalacion Manual del Entorno (Opcional)

Si prefieres usar `main.py` directamente activando tu propio entorno:

```bash
cd features
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Ejecutar con el entorno activo:
python main.py --all
```

---

## 6. Archivos Generados (`features/data/`)

* **`postulantes_listado.csv`**: Tabla maestra con todos los postulantes del sistema.
* **`postulantes_detalle.csv`**: Datos detallados del modal relacionados por `id_postulante`.
* **`checkpoint_listado.json`**: Registro de estado para reanudacion automatica del listado.
* **`checkpoint_detalle.json`**: Registro de estado para reanudacion automatica de los detalles.
