# IDISena

Monorepo del sistema de gestión de recursos humanos y nómina.

## Estructura

- `Backend/`: API Flask y persistencia. Consulta `Backend/README.md` para instalación y ejecución.
- `frontend/`: ubicación de la aplicación web. El framework se definirá al iniciar su implementación.

## Ejecutar el backend

Desde la raíz del repositorio, en PowerShell:

```powershell
Set-Location Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app app db upgrade
python app.py
```
