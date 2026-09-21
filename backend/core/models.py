import uuid
from django.db import models


class Usuario(models.Model):
    ROL_CHOICES = [
        ('USUARIO', 'Usuario'),
        ('ADMIN', 'Administrador'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=120)
    email = models.EmailField(max_length=160, unique=True)
    password_hash = models.CharField(max_length=255)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='USUARIO')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usuarios'

    def __str__(self):
        return self.nombre


class Evento(models.Model):
    ESTADO_CHOICES = [
        ('PUBLICADO', 'Publicado'),
        ('CERRADO', 'Cerrado'),
        ('CANCELADO', 'Cancelado'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=160)
    fecha = models.DateTimeField()
    lugar = models.CharField(max_length=160)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PUBLICADO')

    class Meta:
        db_table = 'eventos'

    def __str__(self):
        return self.nombre


class Asiento(models.Model):
    ESTADO_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('BLOQUEADO', 'Bloqueado'),
        ('VENDIDO', 'Vendido'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='asientos', db_column='evento_id')
    codigo = models.CharField(max_length=20)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='DISPONIBLE')

    class Meta:
        db_table = 'asientos'
        unique_together = ('evento', 'codigo')

    def __str__(self):
        return f"{self.codigo} - {self.evento.nombre}"


class Bloqueo(models.Model):
    ESTADO_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('LIBERADO', 'Liberado'),
        ('CONFIRMADO', 'Confirmado'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asiento = models.OneToOneField(Asiento, on_delete=models.CASCADE, related_name='bloqueo', db_column='asiento_id')
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='bloqueos', db_column='usuario_id')
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_expiracion = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ACTIVO')

    class Meta:
        db_table = 'bloqueos'

    def __str__(self):
        return f"Bloqueo {self.asiento.codigo} ({self.estado})"


class SolicitudCompra(models.Model):
    ESTADO_CHOICES = [
        ('CONFIRMADA', 'Confirmada'),
        ('RECHAZADA', 'Rechazada'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='solicitudes', db_column='usuario_id')
    fecha_hora = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='CONFIRMADA')
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'solicitudes_compra'

    def __str__(self):
        return f"Solicitud {self.id} - {self.usuario.nombre}"


class DetalleCompra(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    solicitud = models.ForeignKey(SolicitudCompra, on_delete=models.CASCADE, related_name='detalles', db_column='solicitud_id')
    asiento = models.OneToOneField(Asiento, on_delete=models.CASCADE, related_name='detalle_compra', db_column='asiento_id')
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'detalle_compra'

    def __str__(self):
        return f"Detalle {self.asiento.codigo}"


class Auditoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    solicitud = models.ForeignKey(SolicitudCompra, on_delete=models.SET_NULL, null=True, blank=True, related_name='auditorias', db_column='solicitud_id')
    bloqueo = models.ForeignKey(Bloqueo, on_delete=models.SET_NULL, null=True, blank=True, related_name='auditorias', db_column='bloqueo_id')
    accion = models.CharField(max_length=80)
    recurso = models.CharField(max_length=120)
    resultado = models.CharField(max_length=30)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auditoria'

    def __str__(self):
        return f"{self.accion} - {self.resultado}"