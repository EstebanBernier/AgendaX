from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    correo = Column(String, unique=True, index=True)
    telefono = Column(String)
    password = Column(String)  # Aquí guardaremos la contraseña encriptada (hash)
    rol = Column(String)       # "cliente", "barbero", "administrador"

class Barbero(Base):
    __tablename__ = "barberos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    telefono = Column(String)
    especialidad = Column(String)

    # Relación con citas
    citas = relationship("Cita", back_populates="barbero")

class Servicio(Base):
    __tablename__ = "servicios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    descripcion = Column(String)
    precio = Column(Float)
    duracion = Column(Integer)  # Duración en minutos (ej. 30, 45)

class Cita(Base):
    __tablename__ = "citas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("usuarios.id"))
    barbero_id = Column(Integer, ForeignKey("barberos.id"))
    servicio_id = Column(Integer, ForeignKey("servicios.id"))
    fecha_hora = Column(String)  # Formato: "YYYY-MM-DD HH:MM"
    estado = Column(String, default="agendada")  # agendada, confirmada, cancelada, completada, no_asistió

    # Relaciones para navegar fácilmente entre objetos en SQLAlchemy
    barbero = relationship("Barbero", back_populates="citas")

class Resena(Base):
    __tablename__ = "resenas"

    id = Column(Integer, primary_key=True, index=True)
    cita_id = Column(Integer, ForeignKey("citas.id"))
    calificacion = Column(Integer)  # 1 a 5 estrellas
    comentario = Column(String, nullable=True)


class Horario(Base):
    """Jornada de un barbero para un día de la semana (0 = lunes ... 6 = domingo).
    Si un barbero NO tiene filas, se usa el horario por defecto 09:00-18:00 todos los días.
    Si tiene filas, los días sin fila son descanso."""
    __tablename__ = "horarios"

    id = Column(Integer, primary_key=True, index=True)
    barbero_id = Column(Integer, ForeignKey("barberos.id"), index=True)
    dia_semana = Column(Integer)   # 0..6
    inicio = Column(String)        # "HH:MM"
    fin = Column(String)           # "HH:MM"
