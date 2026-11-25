FROM python:3.12-slim

WORKDIR /app

COPY payment_service/requirements.txt ./requirements.txt
COPY observability/requirements-tracing.txt .

RUN pip install --no-cache-dir \
    --timeout 120 \
    --retries 10 \
    -r requirements.txt \
    -r requirements-tracing.txt

COPY payment_service/ ./payment_service/
COPY observability /app/observability

CMD ["python", "-m", "payment_service.main"]