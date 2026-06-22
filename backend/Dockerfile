# Stage 1 — builder: install full training tree, plus a slim serving venv
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential g++ libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements-runtime.txt ./

# Full install validates the complete training dependency tree (pandas, scikit-learn, lightgbm, …)
RUN python -m venv /opt/train-venv \
    && /opt/train-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/train-venv/bin/pip install --no-cache-dir -r requirements.txt

# Serving-only venv copied into the runtime image
RUN python -m venv /opt/runtime-venv \
    && /opt/runtime-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/runtime-venv/bin/pip install --no-cache-dir -r requirements-runtime.txt

# Stage 2 — runtime: serving packages + application code + trained models
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/runtime-venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY backend/__init__.py ./backend/__init__.py
COPY backend/app ./backend/app
COPY data/processed/osm_cache.json ./data/processed/osm_cache.json

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Import path is backend.app (not app) because application modules use backend.app.* imports.
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
