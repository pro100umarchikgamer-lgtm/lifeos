FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "backend.production:create_app()", "--bind", "0.0.0.0:8000", "--worker-class", "gthread", "--workers", "2", "--threads", "2", "--timeout", "45", "--max-requests", "2000", "--max-requests-jitter", "200", "--access-logfile", "/dev/null", "--error-logfile", "-"]
