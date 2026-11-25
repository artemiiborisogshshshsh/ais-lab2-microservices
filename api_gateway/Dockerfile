FROM python:3.12-slim

WORKDIR /app

COPY api_gateway/requirements.txt .
COPY observability/requirements-tracing.txt .

RUN pip install --no-cache-dir \
    --timeout 120 \
    --retries 10 \
    -r requirements.txt \
    -r requirements-tracing.txt

COPY api_gateway ./api_gateway
COPY observability /app/observability

CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]