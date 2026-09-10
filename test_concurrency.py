"""
Prueba de concurrencia — Fase 4, criterio 10 / RNF Concurrencia.

Dispara N solicitudes POST /reservas simultáneas contra el MISMO vuelo_instancia_id
+ clase_cabina, que debe tener exactamente 1 asiento disponible antes de correr esto
(usa seed.py o ajusta VUELO_INSTANCIA_ID / CLASE abajo).

Criterio de éxito:
  - Exactamente 1 solicitud recibe 201 (creó el hold).
  - El resto recibe 409 (sin disponibilidad).
  - asientos_disponibles termina en 0 (nunca negativo -> no hubo sobreventa).

Uso:
    python test_concurrency.py                     # contra localhost:8000
    python test_concurrency.py http://EC2_IP:8000   # contra el EC2 del Lab
"""
import asyncio
import sys
from collections import Counter

import asyncpg
import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
N_SOLICITUDES = 20  # mismo N que la RNF de Concurrencia del documento
VUELO_INSTANCIA_ID = 1
CLASE = "ECONOMY"
DSN = "postgresql://postgres:postgres@localhost:5432/testdb"

PAYLOAD = {
    "creado_por_usuario_id": 1,
    "pasajero_id": 1,
    "tramos": [{"vuelo_instancia_id": VUELO_INSTANCIA_ID, "clase_cabina": CLASE}],
    "tipo_tarifa": "BASICA",
}


async def disparar_una(client: httpx.AsyncClient, i: int):
    r = await client.post(f"{BASE_URL}/reservas", json=PAYLOAD)
    return i, r.status_code, r.json()


async def main():
    async with httpx.AsyncClient(timeout=10.0) as client:
        resultados = await asyncio.gather(
            *[disparar_una(client, i) for i in range(N_SOLICITUDES)]
        )

    codigos = Counter(status for _, status, _ in resultados)
    exitosas = [(i, body) for i, status, body in resultados if status == 201]
    rechazadas = [(i, body) for i, status, body in resultados if status == 409]

    print(f"Disparadas {N_SOLICITUDES} solicitudes simultáneas contra "
          f"vuelo_instancia_id={VUELO_INSTANCIA_ID}, clase={CLASE} (1 asiento disponible)\n")
    print(f"Códigos de respuesta: {dict(codigos)}")
    print(f"  201 Created (obtuvieron el hold): {len(exitosas)}")
    print(f"  409 Conflict (sin disponibilidad): {len(rechazadas)}")
    if exitosas:
        i, body = exitosas[0]
        print(f"\nReserva creada: PNR={body.get('codigo_pnr')} (solicitud #{i})")

    # Verificación directa en BD: nunca debe quedar negativo, y debe llegar a 0.
    conn = await asyncpg.connect(DSN)
    disponibles = await conn.fetchval(
        "SELECT asientos_disponibles FROM inventario_asiento "
        "WHERE vuelo_instancia_id = $1 AND clase_cabina = $2",
        VUELO_INSTANCIA_ID, CLASE,
    )
    await conn.close()
    print(f"\nasientos_disponibles en BD tras la prueba: {disponibles}")

    ok = len(exitosas) == 1 and len(rechazadas) == N_SOLICITUDES - 1 and disponibles == 0
    print(f"\n{'✅ PASÓ' if ok else '❌ FALLÓ'}: exactamente 1 hold, "
          f"{N_SOLICITUDES - 1} rechazos, 0 asientos sobrantes, sin sobreventa.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
