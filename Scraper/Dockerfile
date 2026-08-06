# Službeni Playwright image koji već ima Chromium + sve ovisnosti
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# Kopiraj i instaliraj ovisnosti
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiraj cijeli projekt
COPY . .

# Render koristi PORT varijablu okoline
ENV PORT=8000
EXPOSE 8000

# Pokreni server
CMD uvicorn backend.main:app --host 0.0.0.0 --port $PORT