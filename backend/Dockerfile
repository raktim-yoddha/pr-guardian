# ── Stage 1: deps ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS deps

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ───────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from stage 1.
COPY --from=deps /install /usr/local

# Install alembic for auto-migration on startup.
RUN pip install --no-cache-dir alembic

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
