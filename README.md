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

---

## 4. Cargas Masivas (Postulantes y Matriculados)

Permite consultar el historial de subidas de archivos en SIU SUNEDU y descargar directamente sus archivos Excel físicos divididos en 3 carpetas:
* **`originales/`**: Archivo Excel subido originalmente.
* **`validos/`**: Archivo Excel con registros válidos aprobados.
* **`observados/`**: Archivo Excel con errores u observaciones.

### Comandos de Uso:

```bash
# 1. Sincronizar el historial de postulantes y matriculados (genera los CSVs):
python run.py --cargas

# 2. Descargar los archivos Excel (originales, válidos y observados):
python run.py --excels

# 3. Descargar CSVs y Excels a la vez:
python run.py --cargas --excels

# 4. Filtrar por tipo específico si solo deseas uno:
python run.py --cargas --tipo postulantes           # Solo historial CSV de postulantes
python run.py --cargas --tipo matricula             # Solo historial CSV de matrícula
python run.py --excels --tipo postulantes           # Solo Excels de postulantes
python run.py --excels --tipo matricula             # Solo Excels de matrícula

# 5. Descargar solo los Excels con errores/observaciones:
python run.py --excels --solo-observados
```

---

## 5. Opciones Adicionales

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

## 6. Primer Inicio de Sesion y reCAPTCHA en Windows

Si ejecutas por primera vez en Windows o en una maquina donde todavia no existe `auth_session.json`, el sistema debe autenticarse en PUNKU:

* **¿Por que ocurre el timeout en reCAPTCHA?**
  Google reCAPTCHA v2 evalua el navegador. Al ejecutarse en segundo plano (modo oculto o headless), reCAPTCHA abre un desafio visual de seleccion de imagenes (semáforos, pasos peatonales, etc.). Como la ventana no es visible, nadie puede resolverlo y se produce el timeout de 60 segundos.

* **Solucion (Solo la primera vez):**
  1. Ejecuta el comando con ventana visible en tu pantalla:
     ```bash
     python run.py --headed
     ```
  2. Las credenciales se rellenan solas. Si Google solicita resolver las imagenes del captcha, resuelvelas directamente en la ventana abierta.
  3. Una vez ingresado al sistema, se guardara automaticamente el archivo `auth_session.json`.
  4. A partir de ese momento, **la sesion queda guardada** y podras ejecutar siempre en segundo plano (`python run.py --all`) sin ventanas ni captchas.

* **Alternativa rapida:**
  Si ya tienes un archivo `auth_session.json` generado en Linux, copialo dentro de la carpeta `features/` en Windows. El sistema lo reutilizara directamente sin pedir login ni captcha.

---

## 7. Instalacion Manual del Entorno (Opcional)

Si prefieres usar `main.py` directamente activando tu propio entorno:

```bash
# En Linux / macOS:
cd features
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# En Windows (CMD o PowerShell):
cd features
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# Ejecutar con el entorno activo:
python main.py --all
```

---

## 8. Archivos Generados (`features/data/`)

* **`postulantes_listado.csv`**: Tabla maestra con todos los postulantes del sistema.
* **`postulantes_detalle.csv`**: Datos detallados del modal relacionados por `id_postulante`.
* **`cargas_masivas/`**:
  * **`datos_de_postulante/`**:
    * `historial_cargas.csv`: Historial de cargas de postulantes.
    * `originales/`, `validos/`, `observados/`: Archivos Excel físicos descargados.
  * **`datos_de_matricula/`**:
    * `historial_cargas.csv`: Historial de cargas de matrícula.
    * `originales/`, `validos/`, `observados/`: Archivos Excel físicos descargados.
  * `cargas_masivas_consolidado.csv`: Consolidado general.

