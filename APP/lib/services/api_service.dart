import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  // Si corres en Chrome o Windows desktop usamos 127.0.0.1.
  // Si usaras un emulador de Android real, sería 'http://10.0.2.2:8001'
  static const String baseUrl = 'https://agendax-api.onrender.com';

  // 1. INICIAR SESIÓN
  static Future<Map<String, dynamic>?> login(String correo, String password) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/usuarios/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'correo': correo,
          'password': password,
        }),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        return null; // Credenciales inválidas
      }
    } catch (e) {
      print('Error en login: $e');
      return null;
    }
  }

  // 2. REGISTRAR USUARIO
  static Future<bool> registrarUsuario({
    required String nombre,
    required String correo,
    required String telefono,
    required String password,
    String rol = 'cliente',
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/usuarios/registro'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'nombre': nombre,
          'correo': correo,
          'telefono': telefono,
          'password': password,
          'rol': rol,
        }),
      );

      print('Status Code: ${response.statusCode}');
      print('Response Body: ${response.body}');

      return response.statusCode == 201;
    } catch (e) {
      print('Error en registro: $e');
      return false;
    }
  }

  // 3. OBTENER SERVICIOS
  static Future<List<dynamic>> getServicios() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/servicios/'));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      return [];
    } catch (e) {
      print('Error al obtener servicios: $e');
      return [];
    }
  }

  // 4. OBTENER BARBEROS
  static Future<List<dynamic>> getBarberos() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/barberos/'));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      return [];
    } catch (e) {
      print('Error al obtener barberos: $e');
      return [];
    }
  }

  // 5. CREAR CITA (RESERVA)
  static Future<bool> crearCita({
    required int clienteId,
    required int barberoId,
    required int servicioId,
    required String fechaHora,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/citas/'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'cliente_id': clienteId,
          'barbero_id': barberoId,
          'servicio_id': servicioId,
          'fecha_hora': fechaHora,
        }),
      );

      return response.statusCode == 201;
    } catch (e) {
      print('Error al crear cita: $e');
      return false;
    }
  }
}
