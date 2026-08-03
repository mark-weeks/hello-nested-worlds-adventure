# Enfolded — production image for the Fly.io beta.
# See docs/infrastructure/fly-deployment.md for the full deploy runbook.
#
# Two stages: a Node stage compiles the React + PixiJS frontend into
# static/app, then a slim Python stage installs the package and serves
# everything. HOME=/data puts the SQLite store on the mounted volume.

# --- Stage 1: build the React + PixiJS frontend ---
FROM node:20.19-slim AS frontend
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

# Install the locked runtime first so dependency layers remain cacheable without
# pretending an incomplete source tree is an installable project.
COPY requirements.lock ./
RUN pip install -r requirements.lock

# Copy the rest of the source.
COPY . .

# Overlay the freshly built frontend bundle (static/app).
COPY --from=frontend /build/static ./static

# Build/install the application artifact; dependencies are already present.
RUN pip install --no-build-isolation --no-deps .

EXPOSE 8080
CMD ["enfolded", "serve", "--host", "0.0.0.0", "--port", "8080"]
