# Fase 4 — Primera implementación backend

Ya probado de punta a punta en un Postgres local antes de entregarlo:
esquema aplicado sin errores, los 3 endpoints responden, y la prueba de
concurrencia con 20 solicitudes simultáneas dio exactamente 1 hold + 19
rechazos + 0 sobreventa (ver capturas en `docs/`).

Lo que sigue es correr esto mismo contra **tu** RDS/EC2 del Lab — la
evidencia para el criterio 10 tiene que salir de tu entorno, no del mío.

## 1. Aplicar el esquema en tu RDS (`database-3`)

Con DBeaver, igual que verificas los jobs de Glue: abre `schema.sql`
contra la base `testdb` de tu instancia `database-3` y ejecútalo completo.
O desde CloudShell/EC2 con psql:

```bash
psql "host=<endpoint-de-database-3> port=5432 dbname=testdb user=postgres" -f schema.sql
```

## 2. Instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Variables de entorno (apuntando a tu RDS real)

```bash
export DB_HOST=<endpoint-de-database-3>
export DB_PORT=5432
export DB_NAME=testdb
export DB_USER=postgres
export DB_PASSWORD=<tu-password-real>
```

## 4. Sembrar datos mínimos de prueba

`seed.py` trae un ejemplo BOG→MDE con 1 solo asiento ECONOMY (para
poder forzar el escenario del último asiento). Ajusta el DSN dentro
del archivo a tu RDS y corre:

```bash
python seed.py
```

## 5. Levantar la API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Si ya tienes Apache como reverse proxy en el EC2 (como quedó en la
sesión anterior), apunta la ruta correspondiente a este puerto 8000 y
listo — los 3 endpoints quedan expuestos por el mismo dominio/IP.

## 6. Generar tu propia evidencia de concurrencia (criterio 10)

Con la API corriendo y el asiento en 1 disponible:

```bash
python test_concurrency.py http://<tu-ip-o-dominio>:8000
```

El script imprime el conteo de 201 vs 409 y confirma en la BD que
`asientos_disponibles` terminó en 0. Esa salida (cópiala o pantallazo)
es tu evidencia para el documento.

## Endpoints

| Método | Ruta | RF |
|---|---|---|
| GET | `/vuelos?origen=BOG&destino=MDE&fecha=YYYY-MM-DD&pasajeros=N` | RF-03/04 |
| POST | `/reservas` | RF-05 (hold atómico) |
| GET | `/reservas/{codigo_pnr}` | RF-08 |
| GET | `/health` | RNF Disponibilidad |

## Simplificaciones de esta primera implementación

- `tipo_tarifa` se elige para toda la reserva, no por tramo.
- No hay expiración automática del hold todavía (RF-07) ni pago (RF-06)
  — esto es "primera implementación", cubre exactamente lo que pide el
  criterio 9 (los 3 endpoints). RF-06/07 quedan para cuando integres el
  flujo completo.
- El PNR se genera al azar sin loop de reintento ante colisión (con
  32^6 combinaciones, la probabilidad es despreciable para el alcance
  del proyecto).
