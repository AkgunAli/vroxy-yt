# ====================
# Base stage (ortak temel)
# ====================
FROM python:3.10.6-slim AS base

WORKDIR /vroxy

# Sistem bağımlılıkları (gerekliyse – vroxy için genelde gerekmez ama güvenli olsun)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pip'i güncelle + temel araçlar
RUN pip install --upgrade pip setuptools wheel

# requirements.txt kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip show requests urllib3 yt-dlp   # ← build logunda sürüm kontrolü

# Uygulama kodunu kopyala
COPY . .

# Varsayılan komut (production için)
CMD ["python", "-u", "vroxy.py"]

# ====================
# Dev stage (geliştirme için ekstra bağımlılıklar)
# ====================
FROM base AS dev

# Geliştirme bağımlılıkları (lint, test vs. varsa)
COPY requirements_dev.txt ./
RUN pip install --no-cache-dir -r requirements_dev.txt

# Dev modda daha detaylı log için uvicorn yerine direkt python çalıştırabilirsin
CMD ["python", "-u", "vroxy.py"]
