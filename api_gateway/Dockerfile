FROM python:3.12-slim

WORKDIR /app

COPY api_gateway/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY api_gateway ./api_gateway
COPY observability /app/observability
CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
