FROM node:24-bookworm-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 WORK_DIR=/app/runtime \
    WEIGHTS_DIR=/app/weights CACHE_DIR=/app/runtime/perception_cache \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
    MPLCONFIGDIR=/tmp/forte-matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir torch==2.10.0 torchvision==0.25.0 --index-url ${TORCH_INDEX_URL}
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY codex.yaml eval.py models.lock.json ./
COPY --from=ui /ui/dist ./frontend/dist
RUN useradd --uid 10001 --create-home checker \
    && mkdir /app/runtime && chown checker:checker /app/runtime
USER checker
EXPOSE 8000
CMD ["uvicorn", "backend.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
