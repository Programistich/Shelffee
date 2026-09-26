FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY shelffee ./shelffee
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY migrations ./migrations

CMD ["sh", "-c", "alembic upgrade head && python -m shelffee.main"]
