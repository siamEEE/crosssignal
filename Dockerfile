
# Stage 1 — Build the React frontend
FROM node:24-bookworm-slim AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2 — Python API and built frontend
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_PYTHON_DOWNLOADS=0
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY app.py ./

COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

RUN uv sync --frozen --no-dev

EXPOSE 10000

CMD ["sh", "-c", "exec uvicorn crosssignal.api:app --host 0.0.0.0 --port ${PORT:-10000}"]
