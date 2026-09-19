FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY src ./src
COPY web ./web
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1 PORT=8080
CMD exec uvicorn sunosentry.api:app --host 0.0.0.0 --port ${PORT}
