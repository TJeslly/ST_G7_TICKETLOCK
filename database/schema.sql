-- Habilita la generación de UUID automáticos
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Tabla: usuarios
CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'USUARIO' CHECK (rol IN ('USUARIO', 'ADMIN')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tabla: eventos
CREATE TABLE eventos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(160) NOT NULL,
    fecha TIMESTAMPTZ NOT NULL,
    lugar VARCHAR(160) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'PUBLICADO' CHECK (estado IN ('PUBLICADO', 'CERRADO', 'CANCELADO'))
);

-- Tabla: asientos
CREATE TABLE asientos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evento_id UUID NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
    codigo VARCHAR(20) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'DISPONIBLE' CHECK (estado IN ('DISPONIBLE', 'BLOQUEADO', 'VENDIDO')),
    UNIQUE (evento_id, codigo)
);

-- Tabla: bloqueos
CREATE TABLE bloqueos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asiento_id UUID NOT NULL UNIQUE REFERENCES asientos(id) ON DELETE CASCADE,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_inicio TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_expiracion TIMESTAMPTZ NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'LIBERADO', 'CONFIRMADO'))
);

-- Tabla: solicitudes_compra
CREATE TABLE solicitudes_compra (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT now(),
    estado VARCHAR(20) NOT NULL DEFAULT 'CONFIRMADA' CHECK (estado IN ('CONFIRMADA', 'RECHAZADA')),
    total NUMERIC(12,2) NOT NULL CHECK (total >= 0)
);

-- Tabla: detalle_compra
CREATE TABLE detalle_compra (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solicitud_id UUID NOT NULL REFERENCES solicitudes_compra(id) ON DELETE CASCADE,
    asiento_id UUID NOT NULL UNIQUE REFERENCES asientos(id) ON DELETE CASCADE,
    precio_unitario NUMERIC(12,2) NOT NULL CHECK (precio_unitario >= 0)
);

-- Tabla: auditoria
CREATE TABLE auditoria (
    id BIGSERIAL PRIMARY KEY,
    solicitud_id UUID REFERENCES solicitudes_compra(id) ON DELETE SET NULL,
    bloqueo_id UUID REFERENCES bloqueos(id) ON DELETE SET NULL,
    accion VARCHAR(80) NOT NULL,
    recurso VARCHAR(120) NOT NULL,
    resultado VARCHAR(30) NOT NULL,
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices para mejorar las consultas más frecuentes
CREATE INDEX idx_asientos_evento ON asientos(evento_id);
CREATE INDEX idx_bloqueos_usuario ON bloqueos(usuario_id);
CREATE INDEX idx_solicitudes_usuario ON solicitudes_compra(usuario_id);
CREATE INDEX idx_detalle_solicitud ON detalle_compra(solicitud_id);
