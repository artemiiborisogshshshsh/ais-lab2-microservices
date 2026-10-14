
FROM python:3.12-slim

WORKDIR /app

COPY graphql_gateway/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY graphql_gateway/ ./graphql_gateway/

CMD ["uvicorn", "graphql_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
