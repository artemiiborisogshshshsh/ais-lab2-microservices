FROM python:3.12-slim

WORKDIR /app

COPY catalog_service/requirements.txt /app/catalog_service/requirements.txt

RUN pip install --no-cache-dir -r /app/catalog_service/requirements.txt

COPY catalog_service /app/catalog_service

EXPOSE 8000

CMD ["uvicorn", "catalog_service.main:app", "--host", "0.0.0.0", "--port", "8000"]