"""Datos iniciales de AgendaX (idempotente: se puede correr muchas veces).

Crea las tablas y, solo si faltan, los servicios, barberos y cuentas de demo
que usa la app (los mismos de los mockups).

    python seed.py
"""
from database import SessionLocal, engine, Base
import models
from security import hash_password

SERVICIOS = [
    ("Corte clásico", "Acabado tradicional a tijera o máquina", 25000, 30),
    ("Corte + barba", "El servicio completo Delux", 40000, 50),
    ("Afeitado", "Toalla caliente y navaja premium", 18000, 20),
]

# El nombre del usuario-barbero DEBE ser igual al del barbero:
# la app los vincula por nombre al iniciar sesión.
BARBEROS = [
    ("Sandro Barber", "3001110001", "Cortes clásicos", "sandro@delux.com"),
    ("Carlos King", "3001110002", "Barba y afeitado", "carlos@delux.com"),
    ("Mateo Delux", "3001110003", "Cortes modernos", "mateo@delux.com"),
]

PASSWORD_BARBERO = "Barbero123"
ADMIN = ("Administrador Delux", "admin@delux.com", "3000000000", "Admin12345")


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Servicio).count() == 0:
            for nombre, desc, precio, dur in SERVICIOS:
                db.add(models.Servicio(nombre=nombre, descripcion=desc,
                                       precio=precio, duracion=dur))

        for nombre, tel, esp, correo in BARBEROS:
            if not db.query(models.Barbero).filter_by(nombre=nombre).first():
                db.add(models.Barbero(nombre=nombre, telefono=tel, especialidad=esp))
            if not db.query(models.Usuario).filter_by(correo=correo).first():
                db.add(models.Usuario(nombre=nombre, correo=correo, telefono=tel,
                                      password=hash_password(PASSWORD_BARBERO),
                                      rol="barbero"))

        nombre, correo, tel, pw = ADMIN
        if not db.query(models.Usuario).filter_by(correo=correo).first():
            db.add(models.Usuario(nombre=nombre, correo=correo, telefono=tel,
                                  password=hash_password(pw), rol="administrador"))

        db.commit()
        print("Seed listo: servicios, barberos y cuentas de demo verificados.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
