import os
import random
import string
import asyncpg

# Config vía variables de entorno — en el EC2/RDS del Lab solo hay que
# exportar estas 5 variables antes de correr uvicorn (ver README).
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "testdb")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

pool: asyncpg.Pool | None = None


async def connect_pool():
    global pool
    pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        min_size=2,
        max_size=20,  # cubre las >=20 solicitudes concurrentes del RNF de concurrencia
    )


async def close_pool():
    if pool is not None:
        await pool.close()


_PNR_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O/1/I para evitar confusión


def generar_pnr() -> str:
    return "".join(random.choices(_PNR_ALFABETO, k=6))
