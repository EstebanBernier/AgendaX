"""Prueba de punta a punta con las MISMAS llamadas que hace la app Flutter
(http_agenda_repository.dart). Uso:  python test_flujo.py http://127.0.0.1:8001
"""
import sys, json, urllib.request, urllib.parse, urllib.error, time

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8001"
ok = fail = 0

def call(method, path, body=None, query=None, token=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(query) if query else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")

def check(nombre, cond, extra=""):
    global ok, fail
    print(("  OK   " if cond else "  FALLA"), nombre, extra if not cond else "")
    ok += cond; fail += (not cond)

uid = str(int(time.time()))
correo = f"prueba{uid}@correo.com"

s, serv = call("GET", "/servicios/");  check("GET /servicios/ trae 3 servicios", s == 200 and len(serv) >= 3)
s, barb = call("GET", "/barberos/");   check("GET /barberos/ trae 3 barberos", s == 200 and len(barb) >= 3)

s, u = call("POST", "/usuarios/registro", {"nombre": "Cliente Prueba", "correo": correo,
            "telefono": "3001234567", "password": "Clave12345", "rol": "administrador"})
check("registro responde 201", s == 201)
check("registro público NO permite crear administradores", u and u["rol"] == "cliente", f"rol={u and u.get('rol')}")
s, _ = call("POST", "/usuarios/registro", {"nombre": "x", "correo": correo, "telefono": "1", "password": "Clave12345"})
check("correo repetido -> 400", s == 400)

s, l = call("POST", "/usuarios/login", {"correo": correo, "password": "Clave12345"})
check("login cliente devuelve nombre, correo y TELÉFONO", s == 200 and l["usuario"]["rol"] == "cliente" and l["usuario"]["telefono"] == "3001234567" and l["usuario"]["nombre"] == "Cliente Prueba")
check("el registro no devuelve la contraseña", "password" not in u)
s, _ = call("POST", "/usuarios/login", {"correo": correo, "password": "mala"})
check("login con clave mala -> 401", s == 401)
s, lb = call("POST", "/usuarios/login", {"correo": "sandro@delux.com", "password": "Barbero123"})
check("login barbero", s == 200 and lb["usuario"]["rol"] == "barbero")
check("nombre del usuario-barbero coincide con /barberos/",
      lb["usuario"]["nombre"] in [b["nombre"] for b in barb])
s, la = call("POST", "/usuarios/login", {"correo": "admin@delux.com", "password": "Admin12345"})
check("login administrador", s == 200 and la["usuario"]["rol"] == "administrador")

cid = l["usuario"]["id"]; b = barb[0]; sv = serv[0]
fecha = "2026-12-15"
s, d = call("GET", f"/barberos/{b['id']}/disponibilidad", query={"fecha": fecha})
check("disponibilidad devuelve slots 09:00..17:30", s == 200 and len(d["horarios_disponibles"]) == 18)

s, c = call("POST", "/citas/", {"cliente_id": cid, "barbero_id": b["id"], "servicio_id": sv["id"], "fecha_hora": f"{fecha} 11:00"})
check("crear cita -> 201 'agendada'", s == 201 and c["estado"] == "agendada")
s, d = call("GET", f"/barberos/{b['id']}/disponibilidad", query={"fecha": fecha})
check("la hora reservada desaparece de la disponibilidad", "11:00" not in d["horarios_disponibles"])
s, _ = call("POST", "/citas/", {"cliente_id": cid, "barbero_id": b["id"], "servicio_id": sv["id"], "fecha_hora": f"{fecha} 11:00"})
check("doble reserva -> 400 (RNF-006)", s == 400)

s, mine = call("GET", "/citas/", query={"cliente_id": cid})
check("GET /citas/?cliente_id= lista la cita", s == 200 and any(x["id"] == c["id"] for x in mine))
s, mb = call("GET", "/citas/", query={"barbero_id": b["id"]})
check("GET /citas/?barbero_id= (agenda del barbero)", s == 200 and any(x["id"] == c["id"] for x in mb))

s, r = call("PUT", f"/citas/{c['id']}/reprogramar", query={"nueva_fecha_hora": f"{fecha} 12:00"})
check("reprogramar", s == 200 and r["fecha_hora"] == f"{fecha} 12:00")
s, d = call("GET", f"/barberos/{b['id']}/disponibilidad", query={"fecha": fecha})
check("reprogramar libera 11:00 y ocupa 12:00", "11:00" in d["horarios_disponibles"] and "12:00" not in d["horarios_disponibles"])

s, e = call("PUT", f"/citas/{c['id']}/estado", query={"nuevo_estado": "completada"})
check("estado -> completada", s == 200 and e["estado"] == "completada")
s, e = call("PUT", f"/citas/{c['id']}/estado", query={"nuevo_estado": "no_asistió"})
check("estado con tilde 'no_asistió' (query codificada)", s == 200 and e["estado"] == "no_asistió")
s, e = call("PUT", f"/citas/{c['id']}/estado", query={"nuevo_estado": "completada"})

s, rv = call("POST", "/resenas/", {"cita_id": c["id"], "calificacion": 5, "comentario": "Excelente"})
check("crear reseña", s == 201)
s, rs = call("GET", "/resenas/"); check("listar reseñas", s == 200 and any(x["cita_id"] == c["id"] for x in rs))
s, rep = call("GET", "/admin/reportes/ingresos"); check("reporte de ingresos sin token -> 401", s == 401)
s, ad = call("POST", "/admin/login", {"correo": "admin@delux.com", "password": "Admin12345"})
s, rep = call("GET", "/admin/reportes/ingresos", token=ad["token"]); check("reporte de ingresos con token", s == 200 and rep["total_citas_completadas"] >= 1)

s, k = call("PUT", f"/citas/{c['id']}/cancelar")
check("cancelar", s == 200 and k["estado"] == "cancelada")
s, d = call("GET", f"/barberos/{b['id']}/disponibilidad", query={"fecha": fecha})
check("cancelar libera el horario", "12:00" in d["horarios_disponibles"])

print(f"\n{ok} OK, {fail} con falla")
sys.exit(1 if fail else 0)
