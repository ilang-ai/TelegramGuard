FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data

# Cloud Run uses 8080, HF Space uses 7860
ENV PORT=8080
EXPOSE 8080

CMD ["python", "bot.py"]
