# frontend/Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (minimal). Add build-essential only if you need to compile wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install python deps first (better caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy frontend project code
COPY . /app

# Optional: collectstatic at build-time (only if you have static config ready)
# RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Run Django via Gunicorn
CMD ["gunicorn", "frontend_service.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "180", "--graceful-timeout", "30"]
