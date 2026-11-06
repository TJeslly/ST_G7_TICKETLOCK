"""Pasarela de pago SIMULADA (solo con fines académicos).

No se conecta a ningún banco ni procesa dinero real. Valida el formato de una tarjeta
ficticia y simula la respuesta de autorización:

* ``4242 4242 4242 4242``  -> aprobada
* ``4000 0000 0000 0002``  -> rechazada por el banco emisor
* ``4000 0000 0000 9995``  -> rechazada por fondos insuficientes
* cualquier otra tarjeta con número válido (Luhn) -> aprobada

Los datos de la tarjeta viven solo en memoria durante la petición: no se guardan en la
base de datos, ni en la auditoría, ni en los registros del servidor. Del pago solo se
conserva lo que el usuario ve en su comprobante (marca y últimos 4 dígitos).
"""

import re
import secrets
from datetime import date

from .errores import ErrorNegocio

TARJETAS_RECHAZADAS = {
    "4000000000000002": "El banco emisor rechazó la tarjeta. Prueba con otra tarjeta.",
    "4000000000009995": "Fondos insuficientes en la tarjeta. Prueba con otra tarjeta.",
}


def solo_digitos(texto):
    return re.sub(r"[\s-]", "", str(texto or ""))


def luhn_valido(numero):
    """Algoritmo de Luhn: detecta números de tarjeta mal digitados."""
    if not numero.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(numero)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def marca(numero):
    if numero.startswith("4"):
        return "Visa"
    if re.match(r"^(5[1-5]|2[2-7])", numero):
        return "Mastercard"
    if re.match(r"^3[47]", numero):
        return "American Express"
    return "Tarjeta"


def vencimiento_vigente(mes, anio, hoy=None):
    """La tarjeta sirve hasta el último día del mes de vencimiento."""
    hoy = hoy or date.today()
    return (anio, mes) >= (hoy.year, hoy.month)


def autorizar(pago, monto):
    """Simula la autorización. Devuelve el comprobante o lanza ErrorNegocio 402.

    ``pago`` ya viene validado por ``PagoSerializer`` (número limpio, mes y año enteros).
    """
    numero = pago["numero"]
    if numero in TARJETAS_RECHAZADAS:
        raise ErrorNegocio(TARJETAS_RECHAZADAS[numero], 402)
    return {
        "estado": "APROBADO",
        "marca": marca(numero),
        "ultimos4": numero[-4:],
        "autorizacion": "SIM-" + "".join(secrets.choice("0123456789") for _ in range(6)),
        "monto": f"{monto:.2f}",
        "simulado": True,
    }
