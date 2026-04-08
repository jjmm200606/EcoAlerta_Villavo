# venv\Scripts\activate
# python -m uvicorn app.main:app --reload

from pathlib import Path
from datetime import datetime
import shutil
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

# Las tablas se crean manualmente con crear_bd.sql
# Base.metadata.create_all(bind=engine)

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


# Crear admin al iniciar
with SessionLocal() as _db:
    crear_admin_default(_db)


# ───────────── Rutas públicas ─────────────

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request, db: Session = Depends(get_db)):
    actualizar_prioridades(db)
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
    actualizar_prioridades(db)
    usuario = obtener_usuario(request)
    return templates.TemplateResponse(request, "mapa.html", {"usuario": usuario})


@app.get("/api/reportes/geojson")
def reportes_geojson(db: Session = Depends(get_db)):
    """Devolver todos los reportes activos como GeoJSON para Leaflet."""
    actualizar_prioridades(db)
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
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = UPLOADS_DIR / filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(imagen.file, f)
        imagen_path = f"/static/uploads/{filename}"

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
    actualizar_prioridades(db)
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
    actualizar_prioridades(db)
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
    actualizar_prioridades(db)
    usuario = obtener_usuario(request)
    reportes = db.query(Reporte).order_by(Reporte.created_at.desc()).all()
    return templates.TemplateResponse(request, "admin_reportes.html", {
        "usuario": usuario, "reportes": reportes
    })


@app.post("/admin/reportes/actualizar/{reporte_id}")
def actualizar_reporte(
    request: Request,
    reporte_id: int,
    estado: str = Form(...),
    prioridad: str = Form(None),
    comentario: str = Form(""),
    db: Session = Depends(get_db),
):
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
    estado_anterior = reporte.estado
    reporte.estado = estado
    if prioridad and prioridad in {"baja", "media", "alta"}:
        reporte.prioridad = prioridad
    reporte.updated_at = datetime.now()
    db.commit()
    return JSONResponse({"exito": True, "mensaje": "Reporte actualizado"})


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
    actualizar_prioridades(db)
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
