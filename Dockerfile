FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    musl-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar proyecto
COPY . .

# Crear directorios
RUN mkdir -p logs staticfiles media

# Collectstatic
RUN python manage.py collectstatic --noinput --clear || echo "Collectstatic failed, continuing..."

# Exponer puerto
EXPOSE $PORT

# Comando de inicio con logging mejorado
CMD echo "🚀 Starting application..." && \
    echo "📦 Running migrations..." && \
    python manage.py migrate --noinput && \
    echo "✅ Migrations complete" && \
    echo "🌐 Starting Gunicorn on port $PORT..." && \
    gunicorn config.wsgi:application \
        --bind 0.0.0.0:${PORT:-8000} \
        --workers 2 \
        --threads 4 \
        --timeout 0 \
        --keep-alive 5 \
        --log-level debug \
        --access-logfile - \
        --error-logfile - \
        --capture-output