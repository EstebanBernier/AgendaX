import os

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import engine, get_db
import models
import schemas
import horarios
import admin
from security import hash_password, verify_password, require_admin

# Crea las tablas si todavía no existen (necesario en un servidor nuevo)
models.Base.metadata.create_all(bind=engine)

# Inicializacion de la app de FastAPI
app = FastAPI(title="AgendaX API", version="1.1.0")

from fastapi.middleware.cors import CORSMiddleware

# Configurar CORS para permitir peticiones desde Flutter (Web, Desktop, Móvil)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Panel de administración: API (/admin/...) y página web (/admin)
app.include_router(admin.router)

@app.get("/admin", include_in_schema=False)
def panel_admin():
    return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin.html"))

@app.get("/")
def read_root():
    return {"mensaje": "¡Bienvenido a la API de AgendaX (Barbería) con Seguridad y Disponibilidad!"}


# USUARIOS / AUTENTICACIÓN 

@app.post("/usuarios/registro", response_model=schemas.UsuarioResponse, status_code=status.HTTP_201_CREATED)
def registrar_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    # Verificar si el correo ya está registrado
    db_usuario = db.query(models.Usuario).filter(models.Usuario.correo == usuario.correo).first()
    if db_usuario:
        raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado")

    #Encriptar contraseña antes de guardarla
    hashed_pass = hash_password(usuario.password)

    nuevo_usuario = models.Usuario(
        nombre=usuario.nombre,
        correo=usuario.correo,
        telefono=usuario.telefono,
        password=hashed_pass,
        rol="cliente"  # el registro público SIEMPRE crea clientes (barberos/admin los crea seed.py)
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario

@app.post("/usuarios/login")
def login(credenciales: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.correo == credenciales.correo).first()

    # Verificar usuario y contraseña hasheada
    if not usuario or not verify_password(credenciales.password, usuario.password):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    return {
        "mensaje": "Login exitoso",
        "usuario": {
            "id": usuario.id,
            "nombre": usuario.nombre,
            "correo": usuario.correo,
            "telefono": usuario.telefono,
            "rol": usuario.rol
        }
    }


#BARBEROS Y DISPONIBILIDAD

@app.get("/barberos/", response_model=list[schemas.BarberoResponse])
def listar_barberos(db: Session = Depends(get_db)):
    return db.query(models.Barbero).all()

@app.post("/barberos/", response_model=schemas.BarberoResponse, status_code=status.HTTP_201_CREATED)
def crear_barbero(barbero: schemas.BarberoCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    nuevo_barbero = models.Barbero(**barbero.dict())
    db.add(nuevo_barbero)
    db.commit()
    db.refresh(nuevo_barbero)
    return nuevo_barbero

@app.get("/barberos/{barbero_id}/disponibilidad")
def consultar_disponibilidad(barbero_id: int, fecha: str, db: Session = Depends(get_db)):
    """
    RF-004: Horas de inicio libres (cada 30 min) de un barbero en una fecha (AAAA-MM-DD).
    Respeta el horario definido por el administrador (RF-010; por defecto 09:00-18:00)
    y descarta las horas que se cruzan con citas vigentes según su duración.
    """
    barbero = db.query(models.Barbero).filter(models.Barbero.id == barbero_id).first()
    if not barbero:
        raise HTTPException(status_code=404, detail="Barbero no encontrado")

    dia = horarios.parse_fecha(fecha)
    j = horarios.jornada(db, barbero_id, dia)

    return {
        "barbero_id": barbero_id,
        "fecha": fecha,
        "jornada": {"inicio": horarios.a_hhmm(j[0]), "fin": horarios.a_hhmm(j[1])} if j else None,
        "horarios_disponibles": horarios.disponibles(db, barbero_id, dia),
    }


#SERVICIOS 

@app.get("/servicios/", response_model=list[schemas.ServicioResponse])
def listar_servicios(db: Session = Depends(get_db)):
    return db.query(models.Servicio).all()

@app.post("/servicios/", response_model=schemas.ServicioResponse, status_code=status.HTTP_201_CREATED)
def crear_servicio(servicio: schemas.ServicioCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    nuevo_servicio = models.Servicio(**servicio.dict())
    db.add(nuevo_servicio)
    db.commit()
    db.refresh(nuevo_servicio)
    return nuevo_servicio


#CITAS (RESERVAS, REPROGRAMACIÓN, CANCELACIÓN) 

@app.get("/citas/", response_model=list[schemas.CitaResponse])
def listar_citas(barbero_id: int = None, cliente_id: int = None, db: Session = Depends(get_db)):
    query = db.query(models.Cita)
    if barbero_id:
        query = query.filter(models.Cita.barbero_id == barbero_id)
    if cliente_id:
        query = query.filter(models.Cita.cliente_id == cliente_id)
    return query.all()

@app.post("/citas/", response_model=schemas.CitaResponse, status_code=status.HTTP_201_CREATED)
def crear_cita(cita: schemas.CitaCreate, db: Session = Depends(get_db)):
    # RNF-006: evitar doble reserva y respetar horario de atención y duración
    horarios.validar_cita(db, cita.barbero_id, cita.servicio_id, cita.fecha_hora)

    nueva_cita = models.Cita(
        cliente_id=cita.cliente_id,
        barbero_id=cita.barbero_id,
        servicio_id=cita.servicio_id,
        fecha_hora=cita.fecha_hora,
        estado="agendada"
    )
    db.add(nueva_cita)
    db.commit()
    db.refresh(nueva_cita)
    return nueva_cita

@app.put("/citas/{cita_id}/reprogramar", response_model=schemas.CitaResponse)
def reprogramar_cita(cita_id: int, nueva_fecha_hora: str, db: Session = Depends(get_db)):
    """
    RF-006: Permite cambiar la fecha u hora de una cita ya agendada.
    """
    cita = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    # Verificar horario y disponibilidad en la nueva fecha/hora para el mismo barbero
    horarios.validar_cita(db, cita.barbero_id, cita.servicio_id, nueva_fecha_hora, ignorar_cita_id=cita_id)

    cita.fecha_hora = nueva_fecha_hora
    cita.estado = "agendada"  # Opcional: actualizar estado si estaba confirmada
    db.commit()
    db.refresh(cita)
    return cita

@app.put("/citas/{cita_id}/cancelar", response_model=schemas.CitaResponse)
def cancelar_cita(cita_id: int, db: Session = Depends(get_db)):
    """
    RF-007: Permite cancelar una cita agendada y liberar el horario.
    """
    cita = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    cita.estado = "cancelada"
    db.commit()
    db.refresh(cita)
    return cita

@app.put("/citas/{cita_id}/estado", response_model=schemas.CitaResponse)
def actualizar_estado_cita(cita_id: int, nuevo_estado: str, db: Session = Depends(get_db)):
    estados_validos = ["agendada", "confirmada", "cancelada", "completada", "no_asistió"]
    if nuevo_estado not in estados_validos:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Debe ser uno de: {estados_validos}")

    cita = db.query(models.Cita).filter(models.Cita.id == cita_id).first()
    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    cita.estado = nuevo_estado
    db.commit()
    db.refresh(cita)
    return cita


#RESEÑAS

@app.get("/resenas/", response_model=list[schemas.ResenaResponse])
def listar_resenas(db: Session = Depends(get_db)):
    return db.query(models.Resena).all()

@app.post("/resenas/", response_model=schemas.ResenaResponse, status_code=status.HTTP_201_CREATED)
def crear_resena(resena: schemas.ResenaCreate, db: Session = Depends(get_db)):
    cita = db.query(models.Cita).filter(models.Cita.id == resena.cita_id).first()
    if not cita:
        raise HTTPException(status_code=404, detail="La cita especificada no existe")

    nueva_resena = models.Resena(**resena.dict())
    db.add(nueva_resena)
    db.commit()
    db.refresh(nueva_resena)
    return nueva_resena


#REPORTES ADMINISTRATIVOS

@app.get("/admin/reportes/ingresos")
def reporte_ingresos(db: Session = Depends(get_db), _=Depends(require_admin)):
    """
    RF-014: Reporte de ingresos totales basado en citas completadas.
    """
    citas_completadas = db.query(models.Cita).filter(models.Cita.estado == "completada").all()

    ingresos_totales = 0.0
    detalle = []

    for cita in citas_completadas:
        servicio = db.query(models.Servicio).filter(models.Servicio.id == cita.servicio_id).first()
        if servicio:
            ingresos_totales += servicio.precio
            detalle.append({
                "cita_id": cita.id,
                "fecha_hora": cita.fecha_hora,
                "servicio": servicio.nombre,
                "precio": servicio.precio
            })

    return {
        "ingresos_totales": ingresos_totales,
        "total_citas_completadas": len(citas_completadas),
        "detalle": detalle
    }
