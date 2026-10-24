FROM node:24-bookworm-slim@sha256:55fb5f5a527ea2c5c4a95f963e48ef90aa38c7b346054fdc8ee9957a2b55d205 AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TMPDIR=/locks
WORKDIR /app
COPY requirements.lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements.lock.txt
RUN groupadd --gid 10001 atelier && useradd --uid 10001 --gid 10001 --create-home atelier \
    && mkdir /data /locks && chown 10001:10001 /data /locks
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY models/ ./models/
COPY experiments/ ./experiments/
COPY schemas/ ./schemas/
COPY --from=frontend /build/dist ./frontend/dist/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"
CMD ["python", "-m", "uvicorn", "backend.container_main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--timeout-graceful-shutdown", "5"]
