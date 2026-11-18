"""Contraseñas (bcrypt) y sesión del administrador con token firmado que expira (RNF-003)."""
import base64
import hashlib
import hmac
import os
import secrets
import time

import bcrypt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

import models
from database import get_db

# En el servidor define SECRET_KEY; si no, se genera una al arrancar
# (los tokens dejan de valer cuando el servidor se reinicia).
SECRET = (os.environ.get("SECRET_KEY") or secrets.token_hex(32)).encode()
TOKEN_HORAS = 8


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _firmar(payload: str) -> str:
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()


def crear_token(user_id: int) -> str:
    payload = f"{user_id}.{int(time.time()) + TOKEN_HORAS * 3600}"
    return base64.urlsafe_b64encode(payload.encode()).decode() + "." + _firmar(payload)


def leer_token(token: str):
    """Devuelve el id de usuario si el token es válido y no ha expirado; si no, None."""
    try:
        b64, firma = token.split(".")
        payload = base64.urlsafe_b64decode(b64.encode()).decode()
        if not hmac.compare_digest(firma, _firmar(payload)):
            return None
        user_id, exp = payload.split(".")
        return int(user_id) if int(exp) > time.time() else None
    except Exception:
        return None


def require_admin(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Dependencia: exige 'Authorization: Bearer <token>' de un administrador."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Debes iniciar sesión como administrador")
    user_id = leer_token(authorization[7:].strip())
    usuario = db.query(models.Usuario).filter(models.Usuario.id == user_id).first() if user_id else None
    if not usuario or usuario.rol != "administrador":
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada. Inicia sesión de nuevo.")
    return usuario
