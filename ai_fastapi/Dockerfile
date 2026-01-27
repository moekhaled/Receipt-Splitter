FROM python:3.12-slim

WORKDIR /app

# system deps (optional but helpful for curl healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

# Install deps
COPY packages /app/packages
RUN pip install -e /app/packages/receipt_splitter_contracts

COPY ai_fastapi/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# IMPORTANT: install shared contracts package (adjust if you install differently)
COPY packages /app/packages
RUN pip install -e /app/packages/receipt_splitter_contracts

# Copy app code
COPY ai_fastapi /app/ai_fastapi

# Expose the internal port nginx/front/back expect
EXPOSE 8080

# Run FastAPI on 0.0.0.0:8080
CMD ["uvicorn", "ai_fastapi.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
