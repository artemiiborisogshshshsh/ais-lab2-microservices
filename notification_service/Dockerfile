FROM python:3.12-slim

WORKDIR /app

COPY notification_service/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY notification_service/ ./notification_service/

CMD ["python", "-m", "notification_service.main"]