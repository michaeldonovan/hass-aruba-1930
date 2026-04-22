FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY aruba1930api/ aruba1930api/
COPY custom_components/ custom_components/
RUN pip install --no-cache-dir .
CMD ["uvicorn", "aruba1930api.main:app", "--host", "0.0.0.0", "--port", "8000"]
