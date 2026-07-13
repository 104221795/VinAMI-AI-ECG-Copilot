FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md requirements-dev.txt ./

RUN pip install --upgrade pip && pip install -r requirements-dev.txt

COPY src ./src
COPY apps ./apps
COPY migrations ./migrations
COPY scripts ./scripts
COPY tests ./tests
COPY alembic.ini ./

RUN pip install --no-deps .

RUN useradd --create-home --uid 10001 vinami
RUN chown -R vinami:vinami /app
USER vinami
