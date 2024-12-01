# Use Python 3.9 Slim as base image
FROM python:3.9-slim

ENV PYTHONUNBUFFERED True

# Set the working directory
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port 8080 (Cloud Run uses this by default)
EXPOSE 8080

# Use Gunicorn to serve the Flask app
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app:app"]