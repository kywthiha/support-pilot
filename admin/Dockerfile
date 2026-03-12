# Dockerfile for Django Admin Panel
FROM python:3.14-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app
WORKDIR ${APP_HOME}

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Django project code
COPY . ./

# Expose standard Cloud Run port
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} livecustomersupport.wsgi:application"]
