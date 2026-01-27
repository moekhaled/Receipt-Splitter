FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /repo

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY packages/ /repo/packages/
COPY ai/requirements.txt /repo/ai/requirements.txt

WORKDIR /repo/ai
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY ai/ /repo/ai/

EXPOSE 8080

CMD ["gunicorn", "ai_service.wsgi:application", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "2", \
     "--timeout", "180", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
