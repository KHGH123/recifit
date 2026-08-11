FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HOST=0.0.0.0
# Cloud Run injects PORT itself; 8080 matches its default.
ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]
