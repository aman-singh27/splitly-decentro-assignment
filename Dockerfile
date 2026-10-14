# The web build and Django runtime share one origin in the final image.
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY config/ ./config/
COPY ledger/ ./ledger/
COPY manage.py ./
COPY docs/public/ ./docs/public/
COPY --from=web /web/dist ./frontend/dist/
RUN useradd --create-home app && mkdir -p /app/data /app/staticfiles && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && waitress-serve --listen=0.0.0.0:${PORT} config.wsgi:application"]
