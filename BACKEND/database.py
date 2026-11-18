import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Obtener la ruta absoluta del directorio BACKEND
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DB_PATH permite apuntar la base a un disco persistente en el servidor.
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "barberia.db"))
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Engine es el punto de entrada a la base de datos
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# SessionLocal es lo que usaremos para hacer consultas (leer/escribir)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base es de donde heredaremos todos nuestros modelos
Base = declarative_base()


# Dependencia de FastAPI: una sesión de BD por petición
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
