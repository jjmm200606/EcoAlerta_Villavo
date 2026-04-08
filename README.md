# EcoAlerta Villavo

> Plataforma ciudadana de monitoreo de puntos críticos de acumulación de residuos en Villavicencio.  
> Proyecto Hackathon Universitaria 2026.

---

## Tecnologías

| Componente | Tecnología |
|---|---|
| Backend | FastAPI (Python) |
| Base de datos | PostgreSQL (via SQLAlchemy) |
| Frontend | Jinja2 + Bootstrap 5 |
| Mapas | Leaflet.js + MarkerCluster + Leaflet.heat |
| Gráficas | Chart.js |

---

## Instalación rápida

```bash
# 1. Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Poblar con datos de demostración (opcional)
python seed.py

# 4. Iniciar el servidor
python -m uvicorn app.main:app --reload
```

Luego abre: **http://localhost:8000**

---

## Credenciales de demo

| Rol | Email | Contraseña |
|---|---|---|
| Admin | admin@ecoalerta.co | admin1234 |
| Ciudadano | maria@gmail.com | 123456 |
