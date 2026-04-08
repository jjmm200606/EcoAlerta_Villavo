from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import enum


class PrioridadEnum(str, enum.Enum):
    baja = "baja"
    media = "media"
    alta = "alta"


class EstadoReporteEnum(str, enum.Enum):
    pendiente = "pendiente"
    en_proceso = "en_proceso"
    resuelto = "resuelto"


class RolEnum(str, enum.Enum):
    admin = "admin"
    ciudadano = "ciudadano"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    rol = Column(String(20), default="ciudadano")
    estado = Column(String(20), default="activo")
    created_at = Column(DateTime, default=datetime.now)

    reportes = relationship("Reporte", back_populates="usuario")
    votos = relationship("Voto", back_populates="usuario")


class Reporte(Base):
    __tablename__ = "reportes"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=False)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    direccion = Column(String(300))
    barrio = Column(String(150))
    imagen = Column(String(300))
    prioridad = Column(String(20), default="baja")
    estado = Column(String(30), default="pendiente")
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    votos_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    usuario = relationship("Usuario", back_populates="reportes")
    votos = relationship("Voto", back_populates="reporte", cascade="all, delete-orphan")
    historial = relationship("HistorialEstado", back_populates="reporte", cascade="all, delete-orphan")


class Voto(Base):
    """Confirmar que un reporte sigue siendo un problema activo."""
    __tablename__ = "votos"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, ForeignKey("reportes.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)

    reporte = relationship("Reporte", back_populates="votos")
    usuario = relationship("Usuario", back_populates="votos")


class HistorialEstado(Base):
    """Registro de cambios de estado de un reporte."""
    __tablename__ = "historial_estados"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, ForeignKey("reportes.id"), nullable=False)
    estado_anterior = Column(String(30))
    estado_nuevo = Column(String(30))
    comentario = Column(Text)
    admin_email = Column(String(150))
    created_at = Column(DateTime, default=datetime.now)

    reporte = relationship("Reporte", back_populates="historial")
