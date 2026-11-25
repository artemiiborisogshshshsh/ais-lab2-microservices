FROM python:3.12-slim

WORKDIR /app

COPY order_service/requirements.txt ./requirements.txt
COPY observability/requirements-tracing.txt .

RUN pip install --no-cache-dir \
    --timeout 120 \
    --retries 10 \
    -r requirements.txt \
    -r requirements-tracing.txt

COPY order_service/ ./order_service/
COPY observability /app/observability

CMD ["uvicorn", "order_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]