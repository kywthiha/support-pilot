# -----------------------------------------
# Stage 1: Build the Vite React Client
# -----------------------------------------
FROM node:24-bookworm-slim AS client-builder

WORKDIR /app/client
# Copy package manifests and install dependencies
COPY client/package.json client/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

# Copy the rest of the client source and build
COPY client/ ./
RUN pnpm build

# -----------------------------------------
# Stage 2: Runtime FastAPI Agent
# -----------------------------------------
FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app
WORKDIR ${APP_HOME}

# System dependencies (if any required beyond slim)
# RUN apt-get update && apt-get install -y --no-install-recommends ...

# Python dependencies
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server/ ./

# Copy built static files from the client builder
COPY --from=client-builder /app/client/dist ./static

ENV PORT=8080
EXPOSE 8080

# Run Uvicorn via Gunicorn on port 8080
CMD ["gunicorn", "main:app", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080", "--timeout", "0"]
