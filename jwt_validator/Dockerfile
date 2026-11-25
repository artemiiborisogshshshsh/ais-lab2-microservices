FROM python:3.12-slim

WORKDIR /app

COPY jwt_validator/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY jwt_validator /app/jwt_validator
COPY observability /app/observability
CMD ["uvicorn", "jwt_validator.main:app", "--host", "0.0.0.0", "--port", "8000"]