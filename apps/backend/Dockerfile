FROM python:3.12-slim

WORKDIR /app

# Install build dependencies needed for psycopg and other C-extension packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first so Docker can cache this layer
COPY pyproject.toml ./

# Install the project in editable mode with dependencies from pyproject.toml
COPY src ./src
RUN pip install --no-cache-dir -e .

# Copy the rest of the backend (alembic config, migrations)
COPY alembic.ini ./
COPY alembic ./alembic

# Default command runs the API; Worker overrides this via docker-compose
CMD ["uvicorn", "sawakli.api.main:app", "--host", "0.0.0.0", "--port", "8000"]