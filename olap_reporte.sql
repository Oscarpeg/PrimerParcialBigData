-- Reporte OLAP — tabla desnormalizada de reservas para análisis
-- Una fila por tramo reservado (reserva_tramo), con los datos de
-- reserva, vuelo, aeropuertos, tarifa y agencia ya unidos.

CREATE TABLE reporte_reservas (
    reserva_id INT,
    codigo_pnr VARCHAR(6),
    estado VARCHAR(20),
    fecha_creacion TIMESTAMP,
    fecha_pago TIMESTAMP,
    monto_total NUMERIC(10,2),
    agencia_id INT,
    agencia_nombre VARCHAR(255),
    comision_agencia NUMERIC(10,2),
    orden INT,
    clase_cabina VARCHAR(20),
    vuelo_instancia_id INT,
    fecha_vuelo DATE,
    numero_vuelo VARCHAR(20),
    origen CHAR(3),
    destino CHAR(3),
    tipo_tarifa VARCHAR(20),
    precio NUMERIC(10,2)
);

INSERT INTO reporte_reservas (
    reserva_id, codigo_pnr, estado, fecha_creacion, fecha_pago, monto_total,
    agencia_id, agencia_nombre, comision_agencia,
    orden, clase_cabina, vuelo_instancia_id, fecha_vuelo, numero_vuelo,
    origen, destino, tipo_tarifa, precio
)
SELECT
    r.id,
    r.codigo_pnr,
    r.estado::VARCHAR(20),
    r.fecha_creacion,
    r.fecha_pago,
    r.monto_total,
    r.agencia_id,
    ag.nombre,
    r.comision_agencia,
    rt.orden,
    rt.clase_cabina::VARCHAR(20),
    rt.vuelo_instancia_id,
    vi.fecha,
    vp.numero_vuelo,
    ao.codigo_iata,
    ad.codigo_iata,
    t.tipo_tarifa::VARCHAR(20),
    t.precio
FROM reserva r
JOIN reserva_tramo rt   ON rt.reserva_id = r.id
JOIN vuelo_instancia vi ON vi.id = rt.vuelo_instancia_id
JOIN vuelo_plantilla vp ON vp.id = vi.vuelo_plantilla_id
JOIN aeropuerto ao      ON ao.id = vp.aeropuerto_origen_id
JOIN aeropuerto ad      ON ad.id = vp.aeropuerto_destino_id
JOIN tarifa t           ON t.id = rt.tarifa_id
LEFT JOIN agencia ag    ON ag.id = r.agencia_id
ORDER BY r.id, rt.orden;
