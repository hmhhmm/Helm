# Build from the repository root:  docker build -f services/api/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
COPY services/api/pyproject.toml ./
COPY services/api/helm ./helm
COPY contracts/AuditAnchor.json ./contracts/AuditAnchor.json
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "helm.main:app", "--host", "0.0.0.0", "--port", "8000"]
