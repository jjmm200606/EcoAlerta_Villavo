-- =============================================
-- EcoAlerta Villavo - Script de creación de BD
-- PostgreSQL
-- =============================================

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    rol VARCHAR(20) DEFAULT 'ciudadano',
    estado VARCHAR(20) DEFAULT 'activo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reportes (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    descripcion TEXT NOT NULL,
    latitud DOUBLE PRECISION NOT NULL,
    longitud DOUBLE PRECISION NOT NULL,
    direccion VARCHAR(300),
    barrio VARCHAR(150),
    imagen VARCHAR(300),
    prioridad VARCHAR(20) DEFAULT 'baja',
    estado VARCHAR(30) DEFAULT 'pendiente',
    usuario_id INTEGER REFERENCES usuarios(id),
    votos_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS votos (
    id SERIAL PRIMARY KEY,
    reporte_id INTEGER NOT NULL REFERENCES reportes(id) ON DELETE CASCADE,
    usuario_id INTEGER REFERENCES usuarios(id),
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS historial_estados (
    id SERIAL PRIMARY KEY,
    reporte_id INTEGER NOT NULL REFERENCES reportes(id) ON DELETE CASCADE,
    estado_anterior VARCHAR(30),
    estado_nuevo VARCHAR(30),
    comentario TEXT,
    admin_email VARCHAR(150),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Usuarios iniciales
INSERT INTO usuarios (nombre, email, password, rol, estado)
VALUES ('Administrador', 'admin@ecoalerta.co', 'admin1234', 'admin', 'activo')
ON CONFLICT (email) DO NOTHING;

INSERT INTO usuarios (nombre, email, password, rol, estado)
VALUES ('María López', 'maria@gmail.com', '123456', 'ciudadano', 'activo')
ON CONFLICT (email) DO NOTHING;
