FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e . || pip install --no-cache-dir fastapi "uvicorn[standard]" "sqlalchemy>=2" "psycopg[binary]" pydantic numpy ortools httpx
COPY . .
CMD ["uvicorn", "helm.main:app", "--host", "0.0.0.0", "--port", "8000"]
