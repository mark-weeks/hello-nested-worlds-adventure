# Enfolded — production image for the Fly.io beta.
# See docs/infrastructure/fly-deployment.md for the full deploy runbook.
#
# Two stages: a Node stage compiles the React + PixiJS frontend into
# static/app, then a slim Python stage installs the package and serves
# everything. HOME=/data puts the SQLite store on the mounted volume.

# --- Stage 1: build the React + PixiJS frontend ---
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci
COPY frontend ./frontend
COPY static ./static
RUN cd frontend && npm run build   # vite outDir → ../static/app

# --- Stage 2: Python runtime ---
FROM python:3.11-slim
WORKDIR /app

# DB lives at $HOME/.nested-worlds/worlds.db — point HOME at the volume.
ENV HOME=/data \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install Python deps first for layer caching (source not yet present).
COPY pyproject.toml ./
RUN pip install -e . || true

# Copy the rest of the source.
COPY . .

# Overlay the freshly built frontend bundle (static/app).
COPY --from=frontend /build/static ./static

# Reinstall now that the package source is present so the editable
# install picks up the modules.
RUN pip install -e .

EXPOSE 8080
CMD ["python", "main.py", "serve", "--host", "0.0.0.0", "--port", "8080"]
