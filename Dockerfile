FROM python:3.12-slim

WORKDIR /app

# Install pipenv
RUN pip install --no-cache-dir pipenv

# Install dependencies
COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

# Copy application code
COPY . .

# Cloud Run provides PORT env var; default to 8080 for local dev
ENV PORT=8080

CMD exec uvicorn webhook.main:app --host 0.0.0.0 --port "$PORT" --log-level info
