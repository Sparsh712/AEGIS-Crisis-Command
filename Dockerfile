FROM node:22.14.0-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --requirement requirements.lock

COPY backend ./backend
COPY server.py README.md ./
COPY --from=frontend-build /app/frontend/out ./frontend/out

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
