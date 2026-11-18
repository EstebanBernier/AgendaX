"""API del panel de administración (RF-010, RF-011, RF-014 + reseñas y citas)."""
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import horarios as hr
import models
import schemas
from database import get_db
from security import crear_token, hash_password, require_admin, verify_password

router = APIRouter(prefix="/admin", tags=["Administración"])

ESTADOS = ["agendada", "confirmada", "cancelada", "completada", "no_asistió"]


# ------------------------------------------------------------------ login
class AdminLogin(BaseModel):
    correo: str
    password: str


@router.post("/login")
def admin_login(datos: AdminLogin, db: Session = Depends(get_db)):
    u = db.query(models.Usuario).filter(models.Usuario.correo == datos.correo.strip()).first()
    if not u or not verify_password(datos.password, u.password):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    if u.rol != "administrador":
        raise HTTPException(status_code=403, detail="Esta cuenta no es de administrador")
    return {"token": crear_token(u.id), "usuario": {"id": u.id, "nombre": u.nombre, "correo": u.correo}}


# ------------------------------------------------------------------ servicios (RF-011)
@router.post("/servicios", response_model=schemas.ServicioResponse, status_code=201)
def crear_servicio(datos: schemas.ServicioCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    _validar_servicio(datos)
    s = models.Servicio(**datos.dict())
    db.add(s); db.commit(); db.refresh(s)
    return s


@router.put("/servicios/{servicio_id}", response_model=schemas.ServicioResponse)
def editar_servicio(servicio_id: int, datos: schemas.ServicioCreate,
                    db: Session = Depends(get_db), _=Depends(require_admin)):
    _validar_servicio(datos)
    s = db.query(models.Servicio).filter(models.Servicio.id == servicio_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    for k, v in datos.dict().items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return s


@router.delete("/servicios/{servicio_id}")
def eliminar_servicio(servicio_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    s = db.query(models.Servicio).filter(models.Servicio.id == servicio_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    if db.query(models.Cita).filter(models.Cita.servicio_id == servicio_id).count():
        raise HTTPException(status_code=409,
                            detail="Este servicio ya tiene citas registradas; edítalo en lugar de eliminarlo.")
    db.delete(s); db.commit()
    return {"mensaje": "Servicio eliminado"}


def _validar_servicio(d: schemas.ServicioCreate):
    if not d.nombre.strip():
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    if d.precio < 0:
        raise HTTPException(status_code=400, detail="El precio no puede ser negativo")
    if d.duracion < 5 or d.duracion > 480:
        raise HTTPException(status_code=400, detail="La duración debe estar entre 5 y 480 minutos")


# ------------------------------------------------------------------ barberos
class BarberoAdminCreate(BaseModel):
    nombre: str
    telefono: str
    especialidad: str
    correo: str
    password: str


class BarberoAdminUpdate(BaseModel):
    nombre: str
    telefono: str
    especialidad: str


def _usuario_barbero(db: Session, nombre: str):
    # La app vincula usuario <-> barbero por nombre
    return db.query(models.Usuario).filter(
        models.Usuario.nombre == nombre, models.Usuario.rol == "barbero").first()


@router.get("/barberos")
def listar_barberos(db: Session = Depends(get_db), _=Depends(require_admin)):
    res = []
    for b in db.query(models.Barbero).order_by(models.Barbero.id).all():
        u = _usuario_barbero(db, b.nombre)
        res.append({"id": b.id, "nombre": b.nombre, "telefono": b.telefono,
                    "especialidad": b.especialidad, "correo": u.correo if u else None})
    return res


@router.post("/barberos", status_code=201)
def crear_barbero(d: BarberoAdminCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if not d.nombre.strip():
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    if len(d.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener mínimo 8 caracteres")
    if db.query(models.Usuario).filter(models.Usuario.correo == d.correo.strip()).first():
        raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado")
    if db.query(models.Barbero).filter(models.Barbero.nombre == d.nombre.strip()).first():
        raise HTTPException(status_code=400, detail="Ya existe un barbero con ese nombre")
    b = models.Barbero(nombre=d.nombre.strip(), telefono=d.telefono, especialidad=d.especialidad)
    u = models.Usuario(nombre=d.nombre.strip(), correo=d.correo.strip(), telefono=d.telefono,
                       password=hash_password(d.password), rol="barbero")
    db.add_all([b, u]); db.commit(); db.refresh(b)
    return {"id": b.id, "nombre": b.nombre, "telefono": b.telefono,
            "especialidad": b.especialidad, "correo": u.correo}


@router.put("/barberos/{barbero_id}")
def editar_barbero(barbero_id: int, d: BarberoAdminUpdate,
                   db: Session = Depends(get_db), _=Depends(require_admin)):
    b = db.query(models.Barbero).filter(models.Barbero.id == barbero_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Barbero no encontrado")
    nuevo = d.nombre.strip()
    if not nuevo:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    if nuevo != b.nombre and db.query(models.Barbero).filter(models.Barbero.nombre == nuevo).first():
        raise HTTPException(status_code=400, detail="Ya existe un barbero con ese nombre")
    u = _usuario_barbero(db, b.nombre)
    b.nombre, b.telefono, b.especialidad = nuevo, d.telefono, d.especialidad
    if u:
        u.nombre, u.telefono = nuevo, d.telefono   # mantiene el vínculo por nombre
    db.commit()
    return {"id": b.id, "nombre": b.nombre, "telefono": b.telefono, "especialidad": b.especialidad}


@router.delete("/barberos/{barbero_id}")
def eliminar_barbero(barbero_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    b = db.query(models.Barbero).filter(models.Barbero.id == barbero_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Barbero no encontrado")
    if db.query(models.Cita).filter(models.Cita.barbero_id == barbero_id).count():
        raise HTTPException(status_code=409,
                            detail="Este barbero ya tiene citas registradas y no se puede eliminar.")
    u = _usuario_barbero(db, b.nombre)
    db.query(models.Horario).filter(models.Horario.barbero_id == barbero_id).delete()
    if u:
        db.delete(u)
    db.delete(b); db.commit()
    return {"mensaje": "Barbero eliminado"}


# ------------------------------------------------------------------ horarios (RF-010)
class DiaHorario(BaseModel):
    dia_semana: int          # 0 = lunes ... 6 = domingo
    atiende: bool
    inicio: Optional[str] = None
    fin: Optional[str] = None


@router.get("/barberos/{barbero_id}/horarios")
def ver_horarios(barbero_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    if not db.query(models.Barbero).filter(models.Barbero.id == barbero_id).first():
        raise HTTPException(status_code=404, detail="Barbero no encontrado")
    filas = {f.dia_semana: f for f in
             db.query(models.Horario).filter(models.Horario.barbero_id == barbero_id).all()}
    personalizado = bool(filas)
    dias = []
    for d in range(7):
        f = filas.get(d)
        if f:
            dias.append({"dia_semana": d, "atiende": True, "inicio": f.inicio, "fin": f.fin})
        elif not personalizado:   # sin configurar = horario por defecto todos los días
            dias.append({"dia_semana": d, "atiende": True, "inicio": "09:00", "fin": "18:00"})
        else:
            dias.append({"dia_semana": d, "atiende": False, "inicio": "09:00", "fin": "18:00"})
    return {"barbero_id": barbero_id, "personalizado": personalizado, "dias": dias}


@router.put("/barberos/{barbero_id}/horarios")
def guardar_horarios(barbero_id: int, dias: List[DiaHorario],
                     db: Session = Depends(get_db), _=Depends(require_admin)):
    if not db.query(models.Barbero).filter(models.Barbero.id == barbero_id).first():
        raise HTTPException(status_code=404, detail="Barbero no encontrado")
    nuevas = []
    vistos = set()
    for d in dias:
        if d.dia_semana < 0 or d.dia_semana > 6 or d.dia_semana in vistos:
            raise HTTPException(status_code=400, detail="Día de la semana inválido o repetido")
        vistos.add(d.dia_semana)
        if not d.atiende:
            continue
        try:
            ini, fin = hr.a_min(d.inicio), hr.a_min(d.fin)
        except Exception:
            raise HTTPException(status_code=400, detail="Usa horas con formato HH:MM")
        if ini >= fin:
            raise HTTPException(status_code=400, detail="La hora de inicio debe ser menor que la de cierre")
        if fin - ini < hr.PASO:
            raise HTTPException(status_code=400, detail="La jornada debe durar al menos 30 minutos")
        nuevas.append(models.Horario(barbero_id=barbero_id, dia_semana=d.dia_semana,
                                     inicio=hr.a_hhmm(ini), fin=hr.a_hhmm(fin)))
    if not nuevas:
        raise HTTPException(status_code=400, detail="Debe atender al menos un día de la semana")
    db.query(models.Horario).filter(models.Horario.barbero_id == barbero_id).delete()
    db.add_all(nuevas); db.commit()
    return {"mensaje": "Horario guardado"}


# ------------------------------------------------------------------ citas
def _cita_detalle(c, usuarios, barberos, servicios):
    u, b, s = usuarios.get(c.cliente_id), barberos.get(c.barbero_id), servicios.get(c.servicio_id)
    return {
        "id": c.id, "fecha_hora": c.fecha_hora, "estado": c.estado,
        "cliente": u.nombre if u else f"Cliente #{c.cliente_id}",
        "cliente_telefono": u.telefono if u else "",
        "barbero_id": c.barbero_id, "barbero": b.nombre if b else f"Barbero #{c.barbero_id}",
        "servicio": s.nombre if s else "Servicio eliminado",
        "precio": s.precio if s else 0, "duracion": s.duracion if s else 0,
    }


def _catalogos(db):
    return ({u.id: u for u in db.query(models.Usuario).all()},
            {b.id: b for b in db.query(models.Barbero).all()},
            {s.id: s for s in db.query(models.Servicio).all()})


@router.get("/citas")
def listar_citas(fecha: Optional[str] = None, estado: Optional[str] = None,
                 barbero_id: Optional[int] = None,
                 db: Session = Depends(get_db), _=Depends(require_admin)):
    q = db.query(models.Cita)
    if fecha:
        q = q.filter(models.Cita.fecha_hora.like(f"{hr.parse_fecha(fecha).isoformat()}%"))
    if estado:
        q = q.filter(models.Cita.estado == estado)
    if barbero_id:
        q = q.filter(models.Cita.barbero_id == barbero_id)
    cats = _catalogos(db)
    return [_cita_detalle(c, *cats) for c in q.order_by(models.Cita.fecha_hora.desc()).limit(500).all()]


# ------------------------------------------------------------------ reseñas
@router.get("/resenas")
def listar_resenas(db: Session = Depends(get_db), _=Depends(require_admin)):
    cats = _catalogos(db)
    citas = {c.id: c for c in db.query(models.Cita).all()}
    items = []
    for r in db.query(models.Resena).order_by(models.Resena.id.desc()).all():
        c = citas.get(r.cita_id)
        d = _cita_detalle(c, *cats) if c else {}
        items.append({"id": r.id, "cita_id": r.cita_id, "calificacion": r.calificacion,
                      "comentario": r.comentario or "", "cliente": d.get("cliente", ""),
                      "barbero": d.get("barbero", ""), "servicio": d.get("servicio", ""),
                      "fecha_hora": d.get("fecha_hora", "")})
    prom = round(sum(i["calificacion"] for i in items) / len(items), 2) if items else None
    return {"promedio": prom, "total": len(items), "resenas": items}


# ------------------------------------------------------------------ resumen
@router.get("/resumen")
def resumen(db: Session = Depends(get_db), _=Depends(require_admin)):
    ahora = hr.ahora()
    hoy = ahora.date()
    ahora_min = ahora.hour * 60 + ahora.minute
    barberos = db.query(models.Barbero).all()
    activos, libres = 0, 0
    for b in barberos:
        if hr.jornada(db, b.id, hoy) is not None:
            activos += 1
            libres += len(hr.disponibles(db, b.id, hoy, desde_min=ahora_min))
    cats = _catalogos(db)
    citas_hoy = db.query(models.Cita).filter(
        models.Cita.fecha_hora.like(f"{hoy.isoformat()}%"), models.Cita.estado != "cancelada").count()
    proximas = db.query(models.Cita).filter(
        models.Cita.fecha_hora >= ahora.strftime("%Y-%m-%d %H:%M"),
        models.Cita.estado.in_(["agendada", "confirmada"])
    ).order_by(models.Cita.fecha_hora).limit(8).all()
    rs = db.query(models.Resena).all()
    return {
        "fecha": hoy.isoformat(), "citas_hoy": citas_hoy, "espacios_libres": libres,
        "barberos_activos": activos, "barberos_total": len(barberos),
        "resenas_total": len(rs),
        "promedio_resenas": round(sum(r.calificacion for r in rs) / len(rs), 2) if rs else None,
        "proximas": [_cita_detalle(c, *cats) for c in proximas],
    }


# ------------------------------------------------------------------ reportes (RF-014)
@router.get("/reportes")
def reportes(desde: Optional[str] = None, hasta: Optional[str] = None,
             db: Session = Depends(get_db), _=Depends(require_admin)):
    """Ingresos (citas completadas) y ocupación por barbero en un rango de fechas.
    Ocupación = minutos con cita vigente / minutos de jornada en el rango."""
    hoy = hr.ahora().date()
    d_hasta = hr.parse_fecha(hasta) if hasta else hoy
    d_desde = hr.parse_fecha(desde) if desde else d_hasta - timedelta(days=29)
    if d_desde > d_hasta:
        raise HTTPException(status_code=400, detail="'desde' no puede ser posterior a 'hasta'")
    if (d_hasta - d_desde).days > 366:
        raise HTTPException(status_code=400, detail="El rango máximo es de un año")

    servicios = {s.id: s for s in db.query(models.Servicio).all()}
    barberos = db.query(models.Barbero).order_by(models.Barbero.id).all()
    citas = db.query(models.Cita).filter(
        models.Cita.fecha_hora >= f"{d_desde.isoformat()} 00:00",
        models.Cita.fecha_hora <= f"{d_hasta.isoformat()} 23:59").all()

    por_b = {b.id: {"barbero_id": b.id, "nombre": b.nombre, "citas": 0, "completadas": 0,
                    "canceladas": 0, "no_asistio": 0, "ingresos": 0.0,
                    "minutos_ocupados": 0, "minutos_disponibles": 0} for b in barberos}
    por_dia = {}
    d = d_desde
    while d <= d_hasta:
        por_dia[d.isoformat()] = {"fecha": d.isoformat(), "citas": 0, "ingresos": 0.0}
        for b in barberos:
            j = hr.jornada(db, b.id, d)
            if j:
                por_b[b.id]["minutos_disponibles"] += j[1] - j[0]
        d += timedelta(days=1)

    for c in citas:
        fila = por_b.get(c.barbero_id)
        if fila is None:
            continue
        s = servicios.get(c.servicio_id)
        precio, dur = (s.precio, s.duracion) if s else (0, hr.PASO)
        dia = por_dia[c.fecha_hora[:10]]
        if c.estado == "cancelada":
            fila["canceladas"] += 1
            continue
        fila["citas"] += 1
        dia["citas"] += 1
        fila["minutos_ocupados"] += dur
        if c.estado == "completada":
            fila["completadas"] += 1
            fila["ingresos"] += precio
            dia["ingresos"] += precio
        elif c.estado == "no_asistió":
            fila["no_asistio"] += 1

    filas = list(por_b.values())
    for f in filas:
        f["ocupacion_pct"] = round(100 * f["minutos_ocupados"] / f["minutos_disponibles"], 1) \
            if f["minutos_disponibles"] else 0.0
    return {
        "desde": d_desde.isoformat(), "hasta": d_hasta.isoformat(),
        "ingresos_totales": sum(f["ingresos"] for f in filas),
        "citas_totales": sum(f["citas"] for f in filas),
        "completadas": sum(f["completadas"] for f in filas),
        "canceladas": sum(f["canceladas"] for f in filas),
        "no_asistio": sum(f["no_asistio"] for f in filas),
        "por_barbero": filas, "por_dia": list(por_dia.values()),
    }
