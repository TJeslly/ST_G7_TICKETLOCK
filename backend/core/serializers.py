from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from .models import Asiento, Evento, Usuario


class EventoSerializer(serializers.ModelSerializer):
    asientos_disponibles = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = ["id", "nombre", "fecha", "lugar", "estado", "asientos_disponibles"]

    def get_asientos_disponibles(self, obj):
        return obj.asientos.filter(estado="DISPONIBLE").count()


class AsientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asiento
        fields = ["id", "codigo", "estado"]


class RegistroUsuarioSerializer(serializers.Serializer):
    """Valida y crea un usuario (RF01). La contraseña se guarda siempre con hash."""

    nombre = serializers.CharField(
        min_length=2,
        max_length=120,
        error_messages={
            "required": "El nombre es obligatorio.",
            "blank": "El nombre es obligatorio.",
            "min_length": "El nombre debe tener al menos 2 caracteres.",
            "max_length": "El nombre no puede superar 120 caracteres.",
        },
    )
    email = serializers.EmailField(
        max_length=160,
        error_messages={
            "required": "El correo es obligatorio.",
            "blank": "El correo es obligatorio.",
            "invalid": "Ingresa un correo válido.",
            "max_length": "El correo no puede superar 160 caracteres.",
        },
    )
    password = serializers.CharField(
        min_length=8,
        max_length=128,
        write_only=True,
        error_messages={
            "required": "La contraseña es obligatoria.",
            "blank": "La contraseña es obligatoria.",
            "min_length": "La contraseña debe tener al menos 8 caracteres.",
            "max_length": "La contraseña no puede superar 128 caracteres.",
        },
    )

    def validate_nombre(self, value):
        return " ".join(value.split())

    def validate_email(self, value):
        value = value.strip().lower()
        if Usuario.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo.")
        return value

    def validate_password(self, value):
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise serializers.ValidationError(
                "La contraseña debe incluir al menos una letra y un número."
            )
        return value

    def create(self, validated_data):
        return Usuario.objects.create(
            nombre=validated_data["nombre"],
            email=validated_data["email"],
            password_hash=make_password(validated_data["password"]),
            rol="USUARIO",
        )


class LoginSerializer(serializers.Serializer):
    """Credenciales de inicio de sesión (RF02). No revela qué campo falló."""

    email = serializers.EmailField(
        error_messages={
            "required": "El correo es obligatorio.",
            "blank": "El correo es obligatorio.",
            "invalid": "Ingresa un correo válido.",
        }
    )
    password = serializers.CharField(
        max_length=128,
        error_messages={
            "required": "La contraseña es obligatoria.",
            "blank": "La contraseña es obligatoria.",
        },
    )


class UsuarioPublicoSerializer(serializers.ModelSerializer):
    """Datos del usuario que se pueden devolver (nunca el hash)."""

    class Meta:
        model = Usuario
        fields = ["id", "nombre", "email", "rol"]
