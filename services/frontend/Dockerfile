FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn order_splitter.wsgi:application --bind 0.0.0.0:8000"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Project code
COPY . /app

# Run migrations then start
CMD ["sh", "-c", "python manage.py migrate && gunicorn order_splitter.wsgi:application --bind 0.0.0.0:8000"]
