"""Pruebas del panel de administración.  Uso: python test_admin.py http://127.0.0.1:8001"""
import sys, json, urllib.request, urllib.parse, urllib.error, time

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8001"
ok = fail = 0

def call(method, path, body=None, query=None, token=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(query) if query else "")
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            try: return r.status, json.loads(raw)
            except Exception: return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try: return e.code, json.loads(raw)
        except Exception: return e.code, raw

def check(nombre, cond, extra=""):
    global ok, fail
    print(("  OK   " if cond else "  FALLA"), nombre, "" if cond else extra)
    ok += bool(cond); fail += (not cond)

uid = str(int(time.time()))
s, page = call("GET", "/admin"); check("GET /admin sirve la página del panel", s == 200 and "<html" in page.lower())

s, _ = call("GET", "/admin/citas"); check("API admin sin token -> 401", s == 401)
s, _ = call("GET", "/admin/citas", token="basura.firma"); check("token falso -> 401", s == 401)
s, _ = call("POST", "/admin/login", {"correo": "admin@delux.com", "password": "mala"}); check("login admin con clave mala -> 401", s == 401)
s, _ = call("POST", "/admin/login", {"correo": "sandro@delux.com", "password": "Barbero123"}); check("un barbero no entra al panel -> 403", s == 403)
s, ad = call("POST", "/admin/login", {"correo": "admin@delux.com", "password": "Admin12345"}); check("login admin", s == 200 and ad["token"])
T = ad["token"]

# servicios (RF-011)
s, sv = call("POST", "/admin/servicios", {"nombre": "Tinte " + uid, "descripcion": "Color completo", "precio": 60000, "duracion": 60}, token=T)
check("crear servicio", s == 201)
s, sv2 = call("PUT", f"/admin/servicios/{sv['id']}", {"nombre": "Tinte " + uid, "descripcion": "Color", "precio": 65000, "duracion": 90}, token=T)
check("editar servicio (precio y duración)", s == 200 and sv2["precio"] == 65000 and sv2["duracion"] == 90)
s, _ = call("PUT", f"/admin/servicios/{sv['id']}", {"nombre": "x", "descripcion": "", "precio": -1, "duracion": 30}, token=T); check("precio negativo -> 400", s == 400)
s, pub = call("GET", "/servicios/"); check("el cambio se ve en GET /servicios/ (lo que usa la app)", any(x["id"] == sv["id"] and x["precio"] == 65000 for x in pub))
s, _ = call("POST", "/servicios/", {"nombre": "a", "descripcion": "b", "precio": 1, "duracion": 30}); check("POST /servicios/ sin token -> 401", s == 401)

# barberos
s, nb = call("POST", "/admin/barberos", {"nombre": "Barbero " + uid, "telefono": "3009999999", "especialidad": "Fade",
             "correo": f"b{uid}@delux.com", "password": "Clave12345"}, token=T)
check("crear barbero (con su cuenta de acceso)", s == 201 and nb["correo"])
s, lg = call("POST", "/usuarios/login", {"correo": f"b{uid}@delux.com", "password": "Clave12345"})
check("el nuevo barbero puede iniciar sesión", s == 200 and lg["usuario"]["rol"] == "barbero" and lg["usuario"]["nombre"] == nb["nombre"])
s, _ = call("POST", "/admin/barberos", {"nombre": "Otro", "telefono": "1", "especialidad": "x", "correo": f"b{uid}@delux.com", "password": "Clave12345"}, token=T)
check("correo repetido -> 400", s == 400)
s, _ = call("POST", "/admin/barberos", {"nombre": "Otro", "telefono": "1", "especialidad": "x", "correo": "z@z.com", "password": "corta"}, token=T)
check("clave de menos de 8 caracteres -> 400", s == 400)
s, ed = call("PUT", f"/admin/barberos/{nb['id']}", {"nombre": "Barbero Nuevo " + uid, "telefono": "3008888888", "especialidad": "Barba"}, token=T)
check("editar barbero", s == 200)
s, lg = call("POST", "/usuarios/login", {"correo": f"b{uid}@delux.com", "password": "Clave12345"})
check("al renombrar, el usuario sigue vinculado por nombre", lg["usuario"]["nombre"] == ed["nombre"])

# horarios (RF-010): lunes a viernes 10:00-14:00
fecha_lun, fecha_dom = "2026-12-14", "2026-12-20"   # lunes y domingo
s, h = call("GET", f"/admin/barberos/{nb['id']}/horarios", token=T); check("horario por defecto (sin configurar)", s == 200 and not h["personalizado"])
dias = [{"dia_semana": d, "atiende": d < 5, "inicio": "10:00", "fin": "14:00"} for d in range(7)]
s, _ = call("PUT", f"/admin/barberos/{nb['id']}/horarios", dias, token=T); check("guardar horario", s == 200)
s, d = call("GET", f"/barberos/{nb['id']}/disponibilidad", query={"fecha": fecha_lun})
check("disponibilidad respeta 10:00-14:00", d["horarios_disponibles"][0] == "10:00" and d["horarios_disponibles"][-1] == "13:30" and len(d["horarios_disponibles"]) == 8, d)
s, d = call("GET", f"/barberos/{nb['id']}/disponibilidad", query={"fecha": fecha_dom}); check("domingo = descanso (sin horas)", d["horarios_disponibles"] == [])
bad = [dict(x) for x in dias]; bad[0]["inicio"], bad[0]["fin"] = "15:00", "09:00"
s, _ = call("PUT", f"/admin/barberos/{nb['id']}/horarios", bad, token=T); check("inicio >= fin -> 400", s == 400)

# validaciones de cita en el servidor (duración + horario)
s, cl = call("POST", "/usuarios/registro", {"nombre": "Cli " + uid, "correo": f"c{uid}@x.com", "telefono": "3001112222", "password": "Clave12345"})
cid = cl["id"]
srv60 = {"id": sv["id"]}   # 90 min tras la edición
s, _ = call("POST", "/citas/", {"cliente_id": cid, "barbero_id": nb["id"], "servicio_id": sv["id"], "fecha_hora": f"{fecha_lun} 13:00"})
check("servicio de 90 min que termina después del cierre -> 400", s == 400)
s, _ = call("POST", "/citas/", {"cliente_id": cid, "barbero_id": nb["id"], "servicio_id": sv["id"], "fecha_hora": f"{fecha_dom} 11:00"})
check("cita en día de descanso -> 400", s == 400)
s, c1 = call("POST", "/citas/", {"cliente_id": cid, "barbero_id": nb["id"], "servicio_id": sv["id"], "fecha_hora": f"{fecha_lun} 10:00"})
check("cita válida (10:00, 90 min)", s == 201)
s, _ = call("POST", "/citas/", {"cliente_id": cid, "barbero_id": nb["id"], "servicio_id": sv["id"], "fecha_hora": f"{fecha_lun} 11:00"})
check("cita que se cruza por duración (11:00 vs 10:00-11:30) -> 400", s == 400)
s, d = call("GET", f"/barberos/{nb['id']}/disponibilidad", query={"fecha": fecha_lun})
check("disponibilidad bloquea 10:00, 10:30 y 11:00", not set(["10:00", "10:30", "11:00"]) & set(d["horarios_disponibles"]) and "11:30" in d["horarios_disponibles"], d)

# citas / estados / reseñas / reportes
s, lst = call("GET", "/admin/citas", query={"fecha": fecha_lun}, token=T)
fila = next((x for x in lst if x["id"] == c1["id"]), None)
check("listado admin de citas con nombres", s == 200 and fila and fila["cliente"] == "Cli " + uid and fila["barbero"] == ed["nombre"], lst)
s, _ = call("PUT", f"/citas/{c1['id']}/estado", query={"nuevo_estado": "completada"}); check("marcar completada", s == 200)
s, rv = call("POST", "/resenas/", {"cita_id": c1["id"], "calificacion": 4, "comentario": "Muy bien"}); check("reseña del cliente", s == 201)
s, rs = call("GET", "/admin/resenas", token=T)
check("reseñas en el panel (con cliente y barbero)", s == 200 and any(r["cita_id"] == c1["id"] and r["cliente"] == "Cli " + uid for r in rs["resenas"]) and rs["promedio"])
s, rp = call("GET", "/admin/reportes", query={"desde": "2026-12-14", "hasta": "2026-12-20"}, token=T)
fb = next((x for x in rp["por_barbero"] if x["barbero_id"] == nb["id"]), None)
check("reporte: ingresos del barbero = precio del servicio", s == 200 and fb and fb["ingresos"] == 65000 and fb["completadas"] == 1, fb)
check("reporte: ocupación = 90 min de 1200 (5 días × 240) = 7.5 %", fb and fb["minutos_disponibles"] == 1200 and fb["ocupacion_pct"] == 7.5, fb)
check("reporte: serie por día incluye 7 días", len(rp["por_dia"]) == 7)
s, _ = call("GET", "/admin/reportes", query={"desde": "2026-12-20", "hasta": "2026-12-14"}, token=T); check("rango invertido -> 400", s == 400)
s, rm = call("GET", "/admin/resumen", token=T); check("resumen del día", s == 200 and "citas_hoy" in rm and rm["barberos_total"] >= 4)

# bloqueos de borrado
s, _ = call("DELETE", f"/admin/servicios/{sv['id']}", token=T); check("no se elimina un servicio con citas -> 409", s == 409)
s, _ = call("DELETE", f"/admin/barberos/{nb['id']}", token=T); check("no se elimina un barbero con citas -> 409", s == 409)
s, _ = call("PUT", f"/citas/{c1['id']}/cancelar")
s, tmp = call("POST", "/admin/servicios", {"nombre": "Temp " + uid, "descripcion": "x", "precio": 1000, "duracion": 30}, token=T)
s, _ = call("DELETE", f"/admin/servicios/{tmp['id']}", token=T); check("eliminar un servicio sin citas", s == 200)
s, tb = call("POST", "/admin/barberos", {"nombre": "Temp " + uid, "telefono": "1", "especialidad": "x", "correo": f"t{uid}@x.com", "password": "Clave12345"}, token=T)
s, _ = call("DELETE", f"/admin/barberos/{tb['id']}", token=T); check("eliminar un barbero sin citas", s == 200)
s, _ = call("POST", "/usuarios/login", {"correo": f"t{uid}@x.com", "password": "Clave12345"}); check("…y su cuenta también se elimina", s == 401)

print(f"\n{ok} OK, {fail} con falla"); sys.exit(1 if fail else 0)
