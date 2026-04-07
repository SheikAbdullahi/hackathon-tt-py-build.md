FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY server.py .
# Run as root so we can bind to port 443
CMD ["python", "-u", "server.py"]
