# Imagen del backend de TicketLock (Django + Gunicorn).
# Se construye desde la raíz del proyecto: docker compose build
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt gunicorn==23.0.0
COPY backend/ /app/
EXPOSE 8000
CMD ["gunicorn", "ticketlock.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
