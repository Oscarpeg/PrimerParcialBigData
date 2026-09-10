from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


ClaseCabina = Literal["ECONOMY", "BUSINESS"]
TipoTarifa = Literal["BASICA", "FLEX"]


class TramoSolicitado(BaseModel):
    vuelo_instancia_id: int
    clase_cabina: ClaseCabina


class CrearReservaRequest(BaseModel):
    creado_por_usuario_id: int
    pasajero_id: int
    tramos: list[TramoSolicitado] = Field(min_length=1)
    tipo_tarifa: TipoTarifa = "BASICA"
    agencia_id: Optional[int] = None


class ReservaResponse(BaseModel):
    codigo_pnr: str
    estado: str
    monto_total: float
    fecha_creacion: str
    fecha_expiracion_hold: Optional[str] = None
