FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY chamber/ chamber/

RUN pip install --no-cache-dir . && \
    rm -rf /root/.cache

# Non-root user for security
RUN useradd --create-home chamber
USER chamber

ENTRYPOINT ["chamber"]
