# venv\Scripts\activate
# python -m uvicorn app.main:app --reload

from pathlib import Path
from datetime import datetime, timedelta
import base64
import uuid

from fastapi import FastAPI, Form, Request, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import SessionLocal, engine, get_db
from .models import Base, Usuario, Reporte, Voto, HistorialEstado

# Crear tablas automáticamente
Base.metadata.create_all(bind=engine)

app = FastAPI(title="EcoAlerta Villavo")

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "static" / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

app.add_middleware(SessionMiddleware, secret_key="ecoalerta-villavo-2026-hack")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ───────────── Helpers ─────────────

def obtener_usuario(request: Request):
    return request.session.get("usuario")


def requiere_admin(request: Request):
    u = request.session.get("usuario")
    return u and u.get("rol") == "admin"


def calcular_prioridad(votos: int, dias_sin_resolver: int) -> str:
    """Asignar prioridad automática basada en votos y tiempo."""
    score = votos + dias_sin_resolver * 0.5
    if score >= 10:
        return "alta"
    elif score >= 4:
        return "media"
    return "baja"


def actualizar_prioridades(db: Session):
    """Recalcular prioridad de todos los reportes pendientes."""
    ahora = datetime.now()
    reportes = db.query(Reporte).filter(Reporte.estado != "resuelto").all()
    for r in reportes:
        dias = (ahora - r.created_at).days if r.created_at else 0
        r.prioridad = calcular_prioridad(r.votos_count, dias)
    db.commit()


def crear_admin_default(db: Session):
    """Crear usuario administrador si no existe."""
    if not db.query(Usuario).filter(Usuario.email == "admin@ecoalerta.co").first():
        admin = Usuario(
            nombre="Administrador",
            email="admin@ecoalerta.co",
            password="admin1234",
            rol="admin",
        )
        db.add(admin)
        db.commit()
    if not db.query(Usuario).filter(Usuario.email == "maria@gmail.com").first():
        db.add(Usuario(nombre="María López", email="maria@gmail.com", password="123456", rol="ciudadano"))
        db.commit()


def crear_datos_demo(db: Session):
    """Crear reportes de ejemplo si la BD está vacía."""
    if db.query(Reporte).count() > 0:
        return
    ciudadano = db.query(Usuario).filter(Usuario.email == "maria@gmail.com").first()
    uid = ciudadano.id if ciudadano else None

    # SVG placeholder como imagen demo (ícono de basura verde)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" fill="none"><rect width="400" height="300" rx="12" fill="%23e9f5ec"/><text x="200" y="130" text-anchor="middle" font-size="64">🗑️</text><text x="200" y="180" text-anchor="middle" font-family="sans-serif" font-size="16" fill="%23198754">Foto no disponible</text></svg>'
    img_placeholder = f"data:image/svg+xml,{svg}"

    demos = [
        ("Basura acumulada en esquina del Barzal", "Llevan 5 días sin recoger.", 4.1420, -73.6267, "El Barzal", "Cra 35 con Calle 37", "alta", 12, 8),
        ("Escombros en vía principal de La Grama", "Escombros bloqueando el andén.", 4.1365, -73.6312, "La Grama", "Calle 40 con Cra 33", "media", 5, 4),
        ("Contenedor rebosado en el Centro", "No se ha vaciado el contenedor.", 4.1510, -73.6350, "Centro", "Plaza Los Libertadores", "alta", 18, 6),
        ("Bolsas de basura en caño de El Triunfo", "Residentes arrojan basura al caño.", 4.1280, -73.6190, "El Triunfo", "Calle 20 sur", "baja", 2, 3),
        ("Residuos peligrosos cerca del colegio", "Residuos hospitalarios encontrados.", 4.1480, -73.6220, "La Esperanza", "Cra 22 con Calle 44", "alta", 25, 2),
        ("Punto de acopio lleno en Porfía", "No cabe más basura.", 4.1100, -73.6400, "Porfía", "Av. Principal Porfía", "media", 7, 5),
        ("Basura en parque de la Rochela", "Desperdicios de comida y plásticos.", 4.1600, -73.6150, "Rochela", "Parque de la Rochela", "baja", 3, 1),
        ("Llantas abandonadas en lote baldío", "Más de 30 llantas usadas.", 4.1350, -73.6100, "San Antonio", "Calle 15 con Cra 12", "media", 9, 7),
    ]
    for t, desc, lat, lng, barrio, direc, prio, votos, dias in demos:
        db.add(Reporte(
            titulo=t, descripcion=desc, latitud=lat, longitud=lng,
            direccion=direc, barrio=barrio, imagen=img_placeholder, prioridad=prio, estado="pendiente",
            votos_count=votos, usuario_id=uid,
            created_at=datetime.now() - timedelta(days=dias),
        ))
    db.commit()


# Crear admin y datos demo al iniciar
with SessionLocal() as _db:
    # Cambiar columna imagen de VARCHAR(300) a TEXT para soportar base64
    try:
        _db.execute(__import__('sqlalchemy').text("ALTER TABLE reportes ALTER COLUMN imagen TYPE TEXT"))
        _db.commit()
    except Exception:
        _db.rollback()
    crear_admin_default(_db)
    crear_datos_demo(_db)


# ───────────── Rutas públicas ─────────────

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request, db: Session = Depends(get_db)):
    usuario = obtener_usuario(request)
    total = db.query(Reporte).count()
    pendientes = db.query(Reporte).filter(Reporte.estado == "pendiente").count()
    resueltos = db.query(Reporte).filter(Reporte.estado == "resuelto").count()
    alta_prior = db.query(Reporte).filter(Reporte.prioridad == "alta", Reporte.estado != "resuelto").count()
    return templates.TemplateResponse(request, "index.html", {
        "usuario": usuario,
        "total": total,
        "pendientes": pendientes,
        "resueltos": resueltos,
        "alta_prior": alta_prior,
    })


@app.get("/mapa", response_class=HTMLResponse)
def mapa(request: Request, db: Session = Depends(get_db)):
    usuario = obtener_usuario(request)
    return templates.TemplateResponse(request, "mapa.html", {"usuario": usuario})


@app.get("/api/reportes/geojson")
def reportes_geojson(db: Session = Depends(get_db)):
    """Devolver todos los reportes activos como GeoJSON para Leaflet."""
    reportes = db.query(Reporte).filter(Reporte.estado != "resuelto").all()
    features = []
    for r in reportes:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r.longitud, r.latitud]},
            "properties": {
                "id": r.id,
                "titulo": r.titulo,
                "descripcion": r.descripcion,
                "barrio": r.barrio or "",
                "prioridad": r.prioridad,
                "estado": r.estado,
                "votos": r.votos_count,
                "imagen": r.imagen or "",
                "fecha": r.created_at.strftime("%d/%m/%Y") if r.created_at else "",
            }
        })
    return {"type": "FeatureCollection", "features": features}


@app.get("/reportar", response_class=HTMLResponse)
def form_reportar(request: Request):
    usuario = obtener_usuario(request)
    return templates.TemplateResponse(request, "reportar.html", {"usuario": usuario, "error": None, "exito": False})


@app.post("/reportar", response_class=HTMLResponse)
async def crear_reporte(
    request: Request,
    titulo: str = Form(...),
    descripcion: str = Form(...),
    latitud: float = Form(...),
    longitud: float = Form(...),
    direccion: str = Form(""),
    barrio: str = Form(""),
    imagen: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    usuario = obtener_usuario(request)
    imagen_path = None

    if imagen and imagen.filename:
        ext = Path(imagen.filename).suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            return templates.TemplateResponse(request, "reportar.html", {
                "usuario": usuario,
                "error": "Solo se permiten imágenes JPG, PNG o WEBP.", "exito": False
            })
        contenido = await imagen.read()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        tipo = mime.get(ext.lstrip("."), "image/jpeg")
        imagen_path = f"data:{tipo};base64,{base64.b64encode(contenido).decode()}"

    usuario_id = usuario["id"] if usuario else None
    nuevo = Reporte(
        titulo=titulo,
        descripcion=descripcion,
        latitud=latitud,
        longitud=longitud,
        direccion=direccion,
        barrio=barrio,
        imagen=imagen_path,
        prioridad="baja",
        estado="pendiente",
        usuario_id=usuario_id,
    )
    db.add(nuevo)
    db.commit()

    return templates.TemplateResponse(request, "reportar.html", {
        "usuario": usuario,
        "error": None, "exito": True
    })


@app.get("/reportes", response_class=HTMLResponse)
def lista_reportes(request: Request, db: Session = Depends(get_db)):
    usuario = obtener_usuario(request)
    reportes = db.query(Reporte).order_by(Reporte.created_at.desc()).all()
    return templates.TemplateResponse(request, "reportes.html", {
        "usuario": usuario, "reportes": reportes
    })


@app.post("/api/votar/{reporte_id}")
def votar_reporte(reporte_id: int, request: Request, db: Session = Depends(get_db)):
    """Confirmar que un punto de basura sigue siendo un problema (voto ciudadano)."""
    ip = request.client.host if request.client else "0.0.0.0"
    usuario = obtener_usuario(request)
    usuario_id = usuario["id"] if usuario else None

    # Evitar votos duplicados por IP en el mismo reporte
    ya_voto = db.query(Voto).filter(
        Voto.reporte_id == reporte_id,
        Voto.ip_address == ip,
    ).first()
    if ya_voto:
        return JSONResponse({"exito": False, "mensaje": "Ya confirmaste este reporte"})

    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    if not reporte:
        return JSONResponse({"exito": False, "mensaje": "Reporte no encontrado"}, status_code=404)

    voto = Voto(reporte_id=reporte_id, usuario_id=usuario_id, ip_address=ip)
    db.add(voto)
    reporte.votos_count += 1
    reporte.prioridad = calcular_prioridad(reporte.votos_count, (datetime.now() - reporte.created_at).days)
    db.commit()
    return JSONResponse({"exito": True, "votos": reporte.votos_count, "prioridad": reporte.prioridad})


# ───────────── Autenticación ─────────────

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"usuario": None, "error": None})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or usuario.password != password or usuario.estado != "activo":
        return templates.TemplateResponse(request, "login.html", {
            "usuario": None, "error": "Credenciales incorrectas o cuenta inactiva"
        })
    request.session["usuario"] = {"id": usuario.id, "email": usuario.email, "nombre": usuario.nombre, "rol": usuario.rol}
    if usuario.rol == "admin":
        return RedirectResponse(url="/admin", status_code=303)
    return RedirectResponse(url="/mapa", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None, "exito": False})


@app.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    nombre: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    errores = []
    if db.query(Usuario).filter(Usuario.email == email).first():
        errores.append("Este email ya está registrado")
    if password != password_confirm:
        errores.append("Las contraseñas no coinciden")
    if len(password) < 6:
        errores.append("La contraseña debe tener al menos 6 caracteres")
    if not nombre or len(nombre.strip()) < 3:
        errores.append("El nombre debe tener al menos 3 caracteres")
    if "@" not in email or "." not in email:
        errores.append("El email no es válido")
    if errores:
        return templates.TemplateResponse(request, "register.html", {
            "error": " | ".join(errores), "exito": False
        })

    nuevo = Usuario(nombre=nombre, email=email, password=password, rol="ciudadano")
    db.add(nuevo)
    db.commit()
    return templates.TemplateResponse(request, "register.html", {"error": None, "exito": True})


# ───────────── Panel de Administración ─────────────

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request, db: Session = Depends(get_db)):
    if not requiere_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    usuario = obtener_usuario(request)

    total = db.query(Reporte).count()
    pendientes = db.query(Reporte).filter(Reporte.estado == "pendiente").count()
    en_proceso = db.query(Reporte).filter(Reporte.estado == "en_proceso").count()
    resueltos = db.query(Reporte).filter(Reporte.estado == "resuelto").count()
    alta = db.query(Reporte).filter(Reporte.prioridad == "alta", Reporte.estado != "resuelto").count()
    media = db.query(Reporte).filter(Reporte.prioridad == "media", Reporte.estado != "resuelto").count()
    baja = db.query(Reporte).filter(Reporte.prioridad == "baja", Reporte.estado != "resuelto").count()
    total_usuarios = db.query(Usuario).count()

    # Top barrios con más reportes activos
    barrios_raw = (
        db.query(Reporte.barrio, func.count(Reporte.id).label("total"))
        .filter(Reporte.estado != "resuelto", Reporte.barrio != None, Reporte.barrio != "")
        .group_by(Reporte.barrio)
        .order_by(func.count(Reporte.id).desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(request, "admin.html", {
        "usuario": usuario,
        "total": total,
        "pendientes": pendientes,
        "en_proceso": en_proceso,
        "resueltos": resueltos,
        "alta": alta,
        "media": media,
        "baja": baja,
        "total_usuarios": total_usuarios,
        "barrios": barrios_raw,
    })


@app.get("/admin/reportes", response_class=HTMLResponse)
def admin_reportes(request: Request, db: Session = Depends(get_db)):
    if not requiere_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    usuario = obtener_usuario(request)
    reportes = db.query(Reporte).order_by(Reporte.created_at.desc()).all()
    return templates.TemplateResponse(request, "admin_reportes.html", {
        "usuario": usuario, "reportes": reportes
    })


@app.post("/admin/reportes/actualizar/{reporte_id}")
async def actualizar_reporte(
    request: Request,
    reporte_id: int,
    estado: str = Form(...),
    prioridad: str = Form(None),
    comentario: str = Form(""),
    imagen: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    try:
        if not requiere_admin(request):
            return JSONResponse({"error": "No autorizado"}, status_code=403)

        estados_validos = {"pendiente", "en_proceso", "resuelto"}
        if estado not in estados_validos:
            return JSONResponse({"exito": False, "mensaje": "Estado no válido"}, status_code=400)

        reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
        if not reporte:
            return JSONResponse({"exito": False, "mensaje": "Reporte no encontrado"}, status_code=404)

        admin = obtener_usuario(request)
        historial = HistorialEstado(
            reporte_id=reporte_id,
            estado_anterior=reporte.estado,
            estado_nuevo=estado,
            comentario=comentario,
            admin_email=admin["email"] if admin else "",
        )
        db.add(historial)
        reporte.estado = estado
        if prioridad and prioridad in {"baja", "media", "alta"}:
            reporte.prioridad = prioridad
        if imagen and imagen.filename:
            ext = Path(imagen.filename).suffix.lower()
            if ext in {".jpg", ".jpeg", ".png", ".webp"}:
                contenido = await imagen.read()
                mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
                tipo = mime.get(ext.lstrip("."), "image/jpeg")
                reporte.imagen = f"data:{tipo};base64,{base64.b64encode(contenido).decode()}"
        reporte.updated_at = datetime.now()
        db.commit()
        return JSONResponse({"exito": True, "mensaje": "Reporte actualizado"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"exito": False, "mensaje": str(e)}, status_code=500)


@app.post("/admin/reportes/eliminar/{reporte_id}")
def eliminar_reporte(request: Request, reporte_id: int, db: Session = Depends(get_db)):
    if not requiere_admin(request):
        return JSONResponse({"error": "No autorizado"}, status_code=403)
    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    if reporte:
        db.delete(reporte)
        db.commit()
        return JSONResponse({"exito": True})
    return JSONResponse({"exito": False, "mensaje": "No encontrado"}, status_code=404)


@app.get("/admin/usuarios", response_class=HTMLResponse)
def admin_usuarios(request: Request, db: Session = Depends(get_db)):
    if not requiere_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    usuario = obtener_usuario(request)
    usuarios = db.query(Usuario).order_by(Usuario.created_at.desc()).all()
    return templates.TemplateResponse(request, "admin_usuarios.html", {
        "usuario": usuario, "usuarios": usuarios
    })


@app.post("/admin/usuarios/editar/{usuario_id}")
def editar_usuario(
    request: Request,
    usuario_id: int,
    rol: str = Form(...),
    estado: str = Form(...),
    db: Session = Depends(get_db),
):
    if not requiere_admin(request):
        return JSONResponse({"error": "No autorizado"}, status_code=403)
    if rol not in {"admin", "ciudadano"}:
        return JSONResponse({"exito": False, "mensaje": "Rol no válido"}, status_code=400)
    if estado not in {"activo", "inactivo"}:
        return JSONResponse({"exito": False, "mensaje": "Estado no válido"}, status_code=400)

    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not u:
        return JSONResponse({"exito": False, "mensaje": "Usuario no encontrado"}, status_code=404)
    u.rol = rol
    u.estado = estado
    db.commit()
    return JSONResponse({"exito": True, "mensaje": "Usuario actualizado"})


@app.get("/api/estadisticas")
def estadisticas(db: Session = Depends(get_db)):
    """Datos para gráficas del panel admin."""
    por_estado = {
        "pendiente": db.query(Reporte).filter(Reporte.estado == "pendiente").count(),
        "en_proceso": db.query(Reporte).filter(Reporte.estado == "en_proceso").count(),
        "resuelto": db.query(Reporte).filter(Reporte.estado == "resuelto").count(),
    }
    por_prioridad = {
        "alta": db.query(Reporte).filter(Reporte.prioridad == "alta", Reporte.estado != "resuelto").count(),
        "media": db.query(Reporte).filter(Reporte.prioridad == "media", Reporte.estado != "resuelto").count(),
        "baja": db.query(Reporte).filter(Reporte.prioridad == "baja", Reporte.estado != "resuelto").count(),
    }
    barrios = (
        db.query(Reporte.barrio, func.count(Reporte.id).label("total"))
        .filter(Reporte.estado != "resuelto", Reporte.barrio != None, Reporte.barrio != "")
        .group_by(Reporte.barrio)
        .order_by(func.count(Reporte.id).desc())
        .limit(8)
        .all()
    )
    # Puntos del mapa de calor: todos los reportes activos
    calor = db.query(Reporte.latitud, Reporte.longitud, Reporte.votos_count).filter(
        Reporte.estado != "resuelto"
    ).all()

    return JSONResponse({
        "por_estado": por_estado,
        "por_prioridad": por_prioridad,
        "barrios": [{"barrio": b[0], "total": b[1]} for b in barrios],
        "mapa_calor": [{"lat": c[0], "lng": c[1], "peso": c[2] + 1} for c in calor],
    })
