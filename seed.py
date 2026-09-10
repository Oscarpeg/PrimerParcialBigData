"""Siembra datos mínimos para probar los 3 endpoints y el escenario del
último asiento. Pensado para correr una sola vez contra una BD limpia.
"""
import asyncio
import asyncpg

DSN = "postgresql://postgres:postgres@localhost:5432/testdb"


async def main():
    conn = await asyncpg.connect(DSN)

    await conn.execute(
        "INSERT INTO aeropuerto (codigo_iata, ciudad, pais, nombre) VALUES "
        "('BOG','Bogotá','Colombia','El Dorado'), "
        "('MDE','Medellín','Colombia','José María Córdova')"
    )

    plantilla_id = await conn.fetchval(
        """
        INSERT INTO vuelo_plantilla
            (numero_vuelo, aeropuerto_origen_id, aeropuerto_destino_id,
             hora_salida_local, hora_llegada_local, dias_semana,
             fecha_inicio_vigencia, capacidad_economy, capacidad_business)
        VALUES ('AV101',
                (SELECT id FROM aeropuerto WHERE codigo_iata='BOG'),
                (SELECT id FROM aeropuerto WHERE codigo_iata='MDE'),
                '06:00', '07:00', 'LMXJVSD', '2026-09-01', 150, 12)
        RETURNING id
        """
    )

    instancia_id = await conn.fetchval(
        """
        INSERT INTO vuelo_instancia (vuelo_plantilla_id, fecha)
        VALUES ($1, '2026-09-15')
        RETURNING id
        """,
        plantilla_id,
    )

    # ECONOMY con 1 solo asiento disponible -> este es el que usamos
    # para la prueba de concurrencia del último asiento.
    await conn.execute(
        """
        INSERT INTO inventario_asiento
            (vuelo_instancia_id, clase_cabina, asientos_totales, asientos_disponibles)
        VALUES ($1, 'ECONOMY', 150, 1), ($1, 'BUSINESS', 12, 12)
        """,
        instancia_id,
    )

    await conn.execute(
        """
        INSERT INTO tarifa (vuelo_plantilla_id, clase_cabina, tipo_tarifa, precio, precio_neto_agencia)
        VALUES ($1, 'ECONOMY', 'BASICA', 250000, 200000),
               ($1, 'ECONOMY', 'FLEX', 380000, 320000),
               ($1, 'BUSINESS', 'BASICA', 900000, 800000)
        """,
        plantilla_id,
    )

    usuario_id = await conn.fetchval(
        """
        INSERT INTO usuario (email, password_hash, rol)
        VALUES ('pasajero.demo@example.com', 'hash_demo', 'PASAJERO')
        RETURNING id
        """
    )
    await conn.execute(
        """
        INSERT INTO pasajero (usuario_id, nombre, apellido, documento_identidad)
        VALUES ($1, 'Oscar', 'Peñuela', 'CC1000000001')
        """,
        usuario_id,
    )

    await conn.close()
    print(f"Semilla lista. vuelo_instancia_id={instancia_id}, usuario_id={usuario_id}")
    print("Ruta BOG->MDE, 2026-09-15, ECONOMY: 1 solo asiento disponible (para la prueba de concurrencia)")


if __name__ == "__main__":
    asyncio.run(main())
