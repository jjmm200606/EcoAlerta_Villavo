"""Datos de demostración para EcoAlerta Villavo."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from app.database import SessionLocal, engine
from app.models import Base, Usuario, Reporte

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# ── Usuarios ──
if not db.query(Usuario).filter(Usuario.email == "admin@ecoalerta.co").first():
    db.add(Usuario(nombre="Administrador", email="admin@ecoalerta.co", password="admin1234", rol="admin"))
if not db.query(Usuario).filter(Usuario.email == "maria@gmail.com").first():
    db.add(Usuario(nombre="María López", email="maria@gmail.com", password="123456", rol="ciudadano"))
if not db.query(Usuario).filter(Usuario.email == "carlos@gmail.com").first():
    db.add(Usuario(nombre="Carlos Rojas", email="carlos@gmail.com", password="123456", rol="ciudadano"))
if not db.query(Usuario).filter(Usuario.email == "ana@gmail.com").first():
    db.add(Usuario(nombre="Ana Torres", email="ana@gmail.com", password="123456", rol="ciudadano"))
db.commit()

# ── Reportes de ejemplo en Villavicencio ──
reportes_demo = [
    {"titulo": "Basura acumulada en esquina del Barzal", "descripcion": "Llevan 5 días sin recoger los residuos.", "latitud": 4.1420, "longitud": -73.6267, "barrio": "El Barzal", "direccion": "Cra 35 con Calle 37", "prioridad": "alta", "votos_count": 12, "dias": 8},
    {"titulo": "Escombros en vía principal de La Grama", "descripcion": "Escombros de construcción bloqueando el andén.", "latitud": 4.1365, "longitud": -73.6312, "barrio": "La Grama", "direccion": "Calle 40 con Cra 33", "prioridad": "media", "votos_count": 5, "dias": 4},
    {"titulo": "Contenedor rebosado en el Centro", "descripcion": "El contenedor de la plaza no se ha vaciado.", "latitud": 4.1510, "longitud": -73.6350, "barrio": "Centro", "direccion": "Plaza Los Libertadores", "prioridad": "alta", "votos_count": 18, "dias": 6},
    {"titulo": "Bolsas de basura en caño de El Triunfo", "descripcion": "Residentes arrojan basura al caño.", "latitud": 4.1280, "longitud": -73.6190, "barrio": "El Triunfo", "direccion": "Calle 20 sur", "prioridad": "baja", "votos_count": 2, "dias": 3},
    {"titulo": "Residuos peligrosos cerca del colegio", "descripcion": "Se encontraron residuos hospitalarios.", "latitud": 4.1480, "longitud": -73.6220, "barrio": "La Esperanza", "direccion": "Cra 22 con Calle 44", "prioridad": "alta", "votos_count": 25, "dias": 2},
    {"titulo": "Punto de acopio lleno en Porfía", "descripcion": "No cabe más basura en el punto comunitario.", "latitud": 4.1100, "longitud": -73.6400, "barrio": "Porfía", "direccion": "Av. Principal Porfía", "prioridad": "media", "votos_count": 7, "dias": 5},
    {"titulo": "Basura en parque de la Rochela", "descripcion": "Desperdicios de comida y plásticos.", "latitud": 4.1600, "longitud": -73.6150, "barrio": "Rochela", "direccion": "Parque de la Rochela", "prioridad": "baja", "votos_count": 3, "dias": 1},
    {"titulo": "Llantas abandonadas en lote baldío", "descripcion": "Más de 30 llantas usadas en el lote.", "latitud": 4.1350, "longitud": -73.6100, "barrio": "San Antonio", "direccion": "Calle 15 con Cra 12", "prioridad": "media", "votos_count": 9, "dias": 7},
]

ciudadano = db.query(Usuario).filter(Usuario.email == "maria@gmail.com").first()
for r in reportes_demo:
    if not db.query(Reporte).filter(Reporte.titulo == r["titulo"]).first():
        db.add(Reporte(
            titulo=r["titulo"], descripcion=r["descripcion"],
            latitud=r["latitud"], longitud=r["longitud"],
            direccion=r["direccion"], barrio=r["barrio"],
            prioridad=r["prioridad"], estado="pendiente",
            votos_count=r["votos_count"], usuario_id=ciudadano.id if ciudadano else None,
            created_at=datetime.now() - timedelta(days=r["dias"]),
        ))
db.commit()
db.close()
print("✅ Datos de demostración creados exitosamente")
