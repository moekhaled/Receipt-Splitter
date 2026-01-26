FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /repo

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Copy shared contracts first (needed for editable install)
COPY packages/ /repo/packages/

# Copy backend requirements early for caching
COPY backend/requirements.txt /repo/backend/requirements.txt

WORKDIR /repo/backend
RUN pip install --upgrade pip && pip install -r requirements.txt

# Now copy backend source
COPY backend/ /repo/backend/

EXPOSE 8000

# Settings module is provided via docker-compose env
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn order_splitter.wsgi:application --bind 0.0.0.0:8000"]
