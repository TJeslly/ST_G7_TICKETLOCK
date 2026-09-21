-- Usuarios de prueba
INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES
('Admin Demo', 'admin@ticketlock.com', 'hash_demo_admin', 'ADMIN'),
('Usuario Demo', 'usuario@ticketlock.com', 'hash_demo_usuario', 'USUARIO');

-- Evento de prueba
INSERT INTO eventos (nombre, fecha, lugar, estado) VALUES
('Concierto de prueba', '2026-12-01 20:00:00-05', 'Movistar Arena, Bogotá', 'PUBLICADO');

-- Asientos de prueba para ese evento
INSERT INTO asientos (evento_id, codigo, estado)
SELECT id, 'A1', 'DISPONIBLE' FROM eventos WHERE nombre = 'Concierto de prueba'
UNION ALL
SELECT id, 'A2', 'DISPONIBLE' FROM eventos WHERE nombre = 'Concierto de prueba'
UNION ALL
SELECT id, 'A3', 'DISPONIBLE' FROM eventos WHERE nombre = 'Concierto de prueba'
UNION ALL
SELECT id, 'A4', 'DISPONIBLE' FROM eventos WHERE nombre = 'Concierto de prueba';
