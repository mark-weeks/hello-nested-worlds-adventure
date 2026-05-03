#!/bin/bash
set -e

# Python tooling (backend is Python-primary)
pip install uv --quiet

# Node runtime for React + PixiJS frontend
node --version
npm --version

# Frontend dependencies (once package.json exists)
[ -f frontend/package.json ] && cd frontend && npm install && cd ..

echo "Nested World Adventure environment ready ✓"
