-- Sistema de Reservas de Aerolínea — Esquema PostgreSQL
-- Traducido del DBML (Fase 2). Orden respeta dependencias de FK.

-- ===== ENUMS =====
CREATE TYPE rol_usuario AS ENUM ('PASAJERO','AGENTE_AGENCIA','PERSONAL_AEROPUERTO','ADMINISTRADOR');
CREATE TYPE nivel_frecuente AS ENUM ('BASICO','PLATA','ORO','PLATINO');
CREATE TYPE clase_cabina AS ENUM ('ECONOMY','BUSINESS');
CREATE TYPE estado_vuelo AS ENUM ('PROGRAMADO','A_TIEMPO','RETRASADO','CANCELADO','COMPLETADO');
CREATE TYPE tipo_tarifa AS ENUM ('BASICA','FLEX');
CREATE TYPE estado_reserva AS ENUM ('PENDIENTE_PAGO','CONFIRMADA','CANCELADA','EXPIRADA');
CREATE TYPE tipo_transaccion_millas AS ENUM ('ACUMULACION','REDENCION');
CREATE TYPE accion_auditoria AS ENUM ('CREAR','MODIFICAR','CANCELAR','EXPIRAR');

-- ===== ACTORES =====
CREATE TABLE usuario (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol rol_usuario NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE agencia (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    nit VARCHAR(50) UNIQUE NOT NULL,
    comision_pct NUMERIC(5,2) NOT NULL
);

CREATE TABLE aeropuerto (
    id SERIAL PRIMARY KEY,
    codigo_iata CHAR(3) UNIQUE NOT NULL,
    ciudad VARCHAR(255) NOT NULL,
    pais VARCHAR(255) NOT NULL,
    nombre VARCHAR(255) NOT NULL
);

CREATE TABLE pasajero (
    usuario_id INT PRIMARY KEY REFERENCES usuario(id),
    nombre VARCHAR(255) NOT NULL,
    apellido VARCHAR(255) NOT NULL,
    documento_identidad VARCHAR(50) UNIQUE NOT NULL,
    nivel_frecuente nivel_frecuente NOT NULL DEFAULT 'BASICO',
    millas_disponibles INT NOT NULL DEFAULT 0
);

CREATE TABLE agente_agencia (
    usuario_id INT PRIMARY KEY REFERENCES usuario(id),
    agencia_id INT NOT NULL REFERENCES agencia(id)
);

CREATE TABLE personal_aeropuerto (
    usuario_id INT PRIMARY KEY REFERENCES usuario(id),
    aeropuerto_id INT NOT NULL REFERENCES aeropuerto(id)
);

-- ===== RED DE VUELOS =====
CREATE TABLE vuelo_plantilla (
    id SERIAL PRIMARY KEY,
    numero_vuelo VARCHAR(20) NOT NULL,
    aeropuerto_origen_id INT NOT NULL REFERENCES aeropuerto(id),
    aeropuerto_destino_id INT NOT NULL REFERENCES aeropuerto(id),
    hora_salida_local TIME NOT NULL,
    hora_llegada_local TIME NOT NULL,
    dias_semana VARCHAR(7) NOT NULL,
    fecha_inicio_vigencia DATE NOT NULL,
    fecha_fin_vigencia DATE,
    capacidad_economy INT NOT NULL,
    capacidad_business INT NOT NULL
);

CREATE TABLE vuelo_instancia (
    id SERIAL PRIMARY KEY,
    vuelo_plantilla_id INT NOT NULL REFERENCES vuelo_plantilla(id),
    fecha DATE NOT NULL,
    estado_operativo estado_vuelo NOT NULL DEFAULT 'PROGRAMADO',
    UNIQUE (vuelo_plantilla_id, fecha)
);

CREATE TABLE inventario_asiento (
    id SERIAL PRIMARY KEY,
    vuelo_instancia_id INT NOT NULL REFERENCES vuelo_instancia(id),
    clase_cabina clase_cabina NOT NULL,
    asientos_totales INT NOT NULL,
    asientos_disponibles INT NOT NULL CHECK (asientos_disponibles >= 0),
    UNIQUE (vuelo_instancia_id, clase_cabina)
);

CREATE TABLE tarifa (
    id SERIAL PRIMARY KEY,
    vuelo_plantilla_id INT NOT NULL REFERENCES vuelo_plantilla(id),
    clase_cabina clase_cabina NOT NULL,
    tipo_tarifa tipo_tarifa NOT NULL,
    precio NUMERIC(10,2) NOT NULL,
    precio_neto_agencia NUMERIC(10,2)
);

-- ===== RESERVAS =====
CREATE TABLE reserva (
    id SERIAL PRIMARY KEY,
    codigo_pnr VARCHAR(6) UNIQUE NOT NULL,
    creado_por_usuario_id INT NOT NULL REFERENCES usuario(id),
    agencia_id INT REFERENCES agencia(id),
    estado estado_reserva NOT NULL DEFAULT 'PENDIENTE_PAGO',
    fecha_creacion TIMESTAMP NOT NULL DEFAULT now(),
    fecha_expiracion_hold TIMESTAMP,
    fecha_pago TIMESTAMP,
    monto_total NUMERIC(10,2) NOT NULL,
    comision_agencia NUMERIC(10,2)
);

CREATE TABLE reserva_pasajero (
    id SERIAL PRIMARY KEY,
    reserva_id INT NOT NULL REFERENCES reserva(id),
    pasajero_id INT NOT NULL REFERENCES pasajero(usuario_id),
    UNIQUE (reserva_id, pasajero_id)
);

CREATE TABLE reserva_tramo (
    id SERIAL PRIMARY KEY,
    reserva_id INT NOT NULL REFERENCES reserva(id),
    vuelo_instancia_id INT NOT NULL REFERENCES vuelo_instancia(id),
    clase_cabina clase_cabina NOT NULL,
    tarifa_id INT NOT NULL REFERENCES tarifa(id),
    orden INT NOT NULL
);

CREATE TABLE equipaje_adicional (
    id SERIAL PRIMARY KEY,
    reserva_pasajero_id INT NOT NULL REFERENCES reserva_pasajero(id),
    piezas_adicionales INT NOT NULL,
    peso_kg NUMERIC(5,2),
    cargo NUMERIC(10,2) NOT NULL
);

CREATE TABLE transaccion_millas (
    id SERIAL PRIMARY KEY,
    pasajero_id INT NOT NULL REFERENCES pasajero(usuario_id),
    reserva_id INT REFERENCES reserva(id),
    tipo tipo_transaccion_millas NOT NULL,
    cantidad INT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT now()
);

-- ===== AUDITORÍA =====
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    "timestamp" TIMESTAMP NOT NULL DEFAULT now(),
    actor_usuario_id INT REFERENCES usuario(id),
    accion accion_auditoria NOT NULL,
    entidad_tipo VARCHAR(50) NOT NULL,
    entidad_id INT NOT NULL,
    valor_anterior JSONB,
    valor_nuevo JSONB,
    correlation_id VARCHAR(100) NOT NULL
);

-- Índice de apoyo para la búsqueda de vuelos (RF-03)
CREATE INDEX idx_vuelo_instancia_fecha ON vuelo_instancia (fecha);
CREATE INDEX idx_vuelo_plantilla_ruta ON vuelo_plantilla (aeropuerto_origen_id, aeropuerto_destino_id);
