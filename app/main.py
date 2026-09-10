from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import FastAPI, HTTPException

from app.database import connect_pool, close_pool, generar_pnr
from app import database
from app.schemas import CrearReservaRequest, ReservaResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_pool()
    yield
    await close_pool()


app = FastAPI(title="Sistema de Reservas de Aerolínea", lifespan=lifespan)

HOLD_MINUTOS_PASAJERO = 15


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------- RF-03/04: Buscar vuelos ----------
@app.get("/vuelos")
async def buscar_vuelos(origen: str, destino: str, fecha: date, pasajeros: int = 1):
    async with database.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT vi.id AS vuelo_instancia_id, vp.numero_vuelo,
                   ao.codigo_iata AS origen, ad.codigo_iata AS destino,
                   vi.fecha, vp.hora_salida_local, vp.hora_llegada_local,
                   vi.estado_operativo, ia.clase_cabina, ia.asientos_disponibles,
                   t.precio
            FROM vuelo_instancia vi
            JOIN vuelo_plantilla vp ON vp.id = vi.vuelo_plantilla_id
            JOIN aeropuerto ao ON ao.id = vp.aeropuerto_origen_id
            JOIN aeropuerto ad ON ad.id = vp.aeropuerto_destino_id
            JOIN inventario_asiento ia ON ia.vuelo_instancia_id = vi.id
            LEFT JOIN tarifa t ON t.vuelo_plantilla_id = vp.id
                               AND t.clase_cabina = ia.clase_cabina
                               AND t.tipo_tarifa = 'BASICA'
            WHERE ao.codigo_iata = $1 AND ad.codigo_iata = $2 AND vi.fecha = $3
              AND ia.asientos_disponibles >= $4
            ORDER BY vp.hora_salida_local, ia.clase_cabina
            """,
            origen.upper(), destino.upper(), fecha, pasajeros,
        )
        return [
            {
                "vuelo_instancia_id": r["vuelo_instancia_id"],
                "numero_vuelo": r["numero_vuelo"],
                "origen": r["origen"],
                "destino": r["destino"],
                "fecha": r["fecha"].isoformat(),
                "hora_salida_local": r["hora_salida_local"].isoformat(),
                "hora_llegada_local": r["hora_llegada_local"].isoformat(),
                "estado_operativo": r["estado_operativo"],
                "clase_cabina": r["clase_cabina"],
                "asientos_disponibles": r["asientos_disponibles"],
                "precio": float(r["precio"]) if r["precio"] is not None else None,
            }
            for r in rows
        ]


# ---------- RF-05: Crear reserva (hold atómico — B2 de Fase 3) ----------
@app.post("/reservas", response_model=ReservaResponse, status_code=201)
async def crear_reserva(payload: CrearReservaRequest):
    async with database.pool.acquire() as conn:
        async with conn.transaction():
            monto_total = 0.0
            tramos_confirmados = []

            for idx, tramo in enumerate(payload.tramos, start=1):
                # Paso atómico: solo decrementa si hay cupo. 0 filas afectadas = 409.
                fila = await conn.fetchrow(
                    """
                    UPDATE inventario_asiento
                    SET asientos_disponibles = asientos_disponibles - 1
                    WHERE vuelo_instancia_id = $1
                      AND clase_cabina = $2
                      AND asientos_disponibles > 0
                    RETURNING id
                    """,
                    tramo.vuelo_instancia_id, tramo.clase_cabina,
                )
                if fila is None:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Sin disponibilidad en el tramo {idx} "
                               f"(vuelo_instancia_id={tramo.vuelo_instancia_id}, "
                               f"clase={tramo.clase_cabina})",
                    )

                tarifa = await conn.fetchrow(
                    """
                    SELECT t.id, t.precio
                    FROM tarifa t
                    JOIN vuelo_instancia vi ON vi.vuelo_plantilla_id = t.vuelo_plantilla_id
                    WHERE vi.id = $1 AND t.clase_cabina = $2 AND t.tipo_tarifa = $3
                    """,
                    tramo.vuelo_instancia_id, tramo.clase_cabina, payload.tipo_tarifa,
                )
                if tarifa is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No hay tarifa {payload.tipo_tarifa} para el tramo {idx}",
                    )

                monto_total += float(tarifa["precio"])
                tramos_confirmados.append(
                    (tramo.vuelo_instancia_id, tramo.clase_cabina, tarifa["id"], idx)
                )

            codigo_pnr = generar_pnr()
            hold_expira = datetime.utcnow() + timedelta(minutes=HOLD_MINUTOS_PASAJERO)

            reserva = await conn.fetchrow(
                """
                INSERT INTO reserva
                    (codigo_pnr, creado_por_usuario_id, agencia_id, estado,
                     fecha_expiracion_hold, monto_total)
                VALUES ($1, $2, $3, 'PENDIENTE_PAGO', $4, $5)
                RETURNING codigo_pnr, estado, fecha_creacion, fecha_expiracion_hold, monto_total
                """,
                codigo_pnr, payload.creado_por_usuario_id, payload.agencia_id,
                hold_expira, monto_total,
            )

            for vuelo_instancia_id, clase, tarifa_id, orden in tramos_confirmados:
                await conn.execute(
                    """
                    INSERT INTO reserva_tramo
                        (reserva_id, vuelo_instancia_id, clase_cabina, tarifa_id, orden)
                    VALUES ((SELECT id FROM reserva WHERE codigo_pnr = $1), $2, $3, $4, $5)
                    """,
                    codigo_pnr, vuelo_instancia_id, clase, tarifa_id, orden,
                )

            await conn.execute(
                """
                INSERT INTO reserva_pasajero (reserva_id, pasajero_id)
                VALUES ((SELECT id FROM reserva WHERE codigo_pnr = $1), $2)
                """,
                codigo_pnr, payload.pasajero_id,
            )

            return ReservaResponse(
                codigo_pnr=reserva["codigo_pnr"],
                estado=reserva["estado"],
                monto_total=float(reserva["monto_total"]),
                fecha_creacion=reserva["fecha_creacion"].isoformat(),
                fecha_expiracion_hold=reserva["fecha_expiracion_hold"].isoformat(),
            )


# ---------- RF-08: Consultar reserva por PNR ----------
@app.get("/reservas/{codigo_pnr}")
async def consultar_reserva(codigo_pnr: str):
    async with database.pool.acquire() as conn:
        reserva = await conn.fetchrow(
            "SELECT * FROM reserva WHERE codigo_pnr = $1", codigo_pnr.upper()
        )
        if reserva is None:
            raise HTTPException(status_code=404, detail="Reserva no encontrada")

        tramos = await conn.fetch(
            """
            SELECT rt.orden, rt.clase_cabina, vi.fecha, vp.numero_vuelo,
                   ao.codigo_iata AS origen, ad.codigo_iata AS destino, t.precio
            FROM reserva_tramo rt
            JOIN vuelo_instancia vi ON vi.id = rt.vuelo_instancia_id
            JOIN vuelo_plantilla vp ON vp.id = vi.vuelo_plantilla_id
            JOIN aeropuerto ao ON ao.id = vp.aeropuerto_origen_id
            JOIN aeropuerto ad ON ad.id = vp.aeropuerto_destino_id
            JOIN tarifa t ON t.id = rt.tarifa_id
            WHERE rt.reserva_id = $1
            ORDER BY rt.orden
            """,
            reserva["id"],
        )

        return {
            "codigo_pnr": reserva["codigo_pnr"],
            "estado": reserva["estado"],
            "monto_total": float(reserva["monto_total"]),
            "fecha_creacion": reserva["fecha_creacion"].isoformat(),
            "fecha_expiracion_hold": (
                reserva["fecha_expiracion_hold"].isoformat()
                if reserva["fecha_expiracion_hold"] else None
            ),
            "tramos": [
                {
                    "orden": t["orden"],
                    "vuelo": t["numero_vuelo"],
                    "clase": t["clase_cabina"],
                    "origen": t["origen"],
                    "destino": t["destino"],
                    "fecha": t["fecha"].isoformat(),
                    "precio": float(t["precio"]),
                }
                for t in tramos
            ],
        }
