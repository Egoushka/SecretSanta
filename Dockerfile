FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,signal; os.kill(1,0)"

CMD ["python", "main.py"]
