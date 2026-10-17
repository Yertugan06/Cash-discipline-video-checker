# Gateway image = checker image + a WebSocket library for uvicorn.
# Build from the repo root: docker build -f realtime/Dockerfile --build-arg BASE=forte-cash-checker:cuda -t datathon26-realtime .
ARG BASE=forte-cash-checker:cpu
FROM ${BASE}
USER root
COPY realtime/requirements.txt /tmp/realtime-requirements.txt
RUN pip install --no-cache-dir -r /tmp/realtime-requirements.txt
COPY realtime /app/realtime
WORKDIR /app
USER checker
CMD ["python", "-m", "uvicorn", "--factory", "realtime.gateway:create_app", "--host", "127.0.0.1", "--port", "8100"]
