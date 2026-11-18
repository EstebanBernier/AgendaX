from pydantic import BaseModel
from typing import Optional

#USUARIOS
class UsuarioCreate(BaseModel):
    nombre: str
    correo: str
    telefono: str
    password: str
    rol: str = "cliente"  # por defecto tiene que ser cliente

class UsuarioResponse(BaseModel):
    """Datos públicos del usuario: nunca incluye la contraseña."""
    id: int
    nombre: str
    correo: str
    telefono: str
    rol: str

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    correo: str
    password: str


#BARBEROS
class BarberoCreate(BaseModel):
    nombre: str
    telefono: str
    especialidad: str

class BarberoResponse(BarberoCreate):
    id: int

    class Config:
        from_attributes = True


#SERVICIOS
class ServicioCreate(BaseModel):
    nombre: str
    descripcion: str
    precio: float
    duracion: int  # en minutos

class ServicioResponse(ServicioCreate):
    id: int

    class Config:
        from_attributes = True


#CITAS
class CitaCreate(BaseModel):
    cliente_id: int
    barbero_id: int
    servicio_id: int
    fecha_hora: str  

class CitaResponse(CitaCreate):
    id: int
    estado: str

    class Config:
        from_attributes = True


#RESEÑAS 
class ResenaCreate(BaseModel):
    cita_id: int
    calificacion: int  # 1 a 5
    comentario: Optional[str] = None

class ResenaResponse(ResenaCreate):
    id: int

    class Config:
        from_attributes = True
