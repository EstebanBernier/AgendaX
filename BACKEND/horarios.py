"""Reglas de horario y disponibilidad (RF-004, RF-010, RNF-006)."""
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models

PASO = 30                       # minutos entre horas de inicio
DEFAULT_INI, DEFAULT_FIN = 540, 1080   # 09:00 - 18:00
TZ = timezone(timedelta(hours=-5))     # Colombia (el servidor suele estar en UTC)


def ahora() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def a_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def a_hhmm(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def parse_fecha(texto: str) -> date:
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida. Usa el formato AAAA-MM-DD")


def jornada(db: Session, barbero_id: int, dia: date):
    """(inicio, fin) en minutos, o None si el barbero descansa ese día."""
    filas = db.query(models.Horario).filter(models.Horario.barbero_id == barbero_id).all()
    if not filas:
        return DEFAULT_INI, DEFAULT_FIN
    fila = next((f for f in filas if f.dia_semana == dia.weekday()), None)
    if not fila:
        return None
    return a_min(fila.inicio), a_min(fila.fin)


def _duraciones(db: Session) -> dict:
    return {s.id: (s.duracion or PASO) for s in db.query(models.Servicio).all()}


def ocupados(db: Session, barbero_id: int, dia: date, ignorar_cita_id=None):
    """Intervalos (inicio, fin) en minutos de las citas vigentes de ese día."""
    dur = _duraciones(db)
    citas = db.query(models.Cita).filter(
        models.Cita.barbero_id == barbero_id,
        models.Cita.fecha_hora.like(f"{dia.isoformat()}%"),
        models.Cita.estado != "cancelada",
    ).all()
    res = []
    for c in citas:
        if ignorar_cita_id is not None and c.id == ignorar_cita_id:
            continue
        ini = a_min(c.fecha_hora[11:16])
        res.append((ini, ini + dur.get(c.servicio_id, PASO)))
    return res


def disponibles(db: Session, barbero_id: int, dia: date, desde_min: int = None):
    """Horas de inicio libres (cada 30 min) dentro de la jornada."""
    j = jornada(db, barbero_id, dia)
    if j is None:
        return []
    ini, fin = j
    busy = ocupados(db, barbero_id, dia)
    libres = []
    for t in range(ini, fin - PASO + 1, PASO):
        if desde_min is not None and t <= desde_min:
            continue
        if any(t < b_fin and t + PASO > b_ini for b_ini, b_fin in busy):
            continue
        libres.append(a_hhmm(t))
    return libres


def validar_cita(db: Session, barbero_id: int, servicio_id: int, fecha_hora: str, ignorar_cita_id=None):
    """Lanza 400/404 si la cita no cabe en la jornada o choca con otra (por duración)."""
    try:
        inicio = datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="fecha_hora inválida. Usa 'AAAA-MM-DD HH:MM'")

    servicio = db.query(models.Servicio).filter(models.Servicio.id == servicio_id).first()
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    if not db.query(models.Barbero).filter(models.Barbero.id == barbero_id).first():
        raise HTTPException(status_code=404, detail="Barbero no encontrado")

    dia = inicio.date()
    j = jornada(db, barbero_id, dia)
    if j is None:
        raise HTTPException(status_code=400, detail="El barbero no atiende ese día.")

    ini = inicio.hour * 60 + inicio.minute
    fin = ini + (servicio.duracion or PASO)
    if ini < j[0] or fin > j[1]:
        raise HTTPException(
            status_code=400,
            detail=f"Fuera del horario de atención ({a_hhmm(j[0])} - {a_hhmm(j[1])}).",
        )

    for b_ini, b_fin in ocupados(db, barbero_id, dia, ignorar_cita_id):
        if ini < b_fin and fin > b_ini:
            raise HTTPException(
                status_code=400,
                detail="El barbero ya tiene una cita reservada en este horario. Por favor elija otra hora.",
            )
