FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY src ./src
COPY config ./config
COPY openapi_json ./openapi_json

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "gateway_framework.main"]
