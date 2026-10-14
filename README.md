# API Flask con SQLite

## Iniciar en Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

La API queda disponible en http://127.0.0.1:5000. La base de datos se crea
automáticamente en `instance/items.sqlite3`.

## Estructura

- `models/`: modelo `Item` y consultas SQLite.
- `services/`: validación y lógica de negocio.
- `controllers/`: conversión entre solicitudes HTTP y respuestas JSON.
- `routes/`: rutas de Flask para `/api/items`.
- `database.py`: conexión, cierre e inicialización de SQLite.
- `app.py`: creación y configuración de la aplicación.

## Endpoints

- `GET /api/items`: listar elementos.
- `POST /api/items`: crear un elemento con `name` y, opcionalmente, `description`.
- `GET /api/items/<id>`: obtener un elemento.
- `PATCH /api/items/<id>`: actualizar `name` o `description`.
- `DELETE /api/items/<id>`: eliminar un elemento.

Ejemplo de cuerpo para crear un elemento:

```json
{
	"name": "Mi elemento",
	"description": "Descripción opcional"
}
```