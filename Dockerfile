# ====================
# Base stage (ortak temel – üretim için temiz image)
# ====================
FROM python:3.10.6-slim AS base

# Çalışma dizini
WORKDIR /vroxy

# Sistem bağımlılıkları (vroxy için curl ve ca-certificates yeterli olur)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pip'i güncelle (çatışma çözümü için zorunlu)
RUN pip install --upgrade pip setuptools wheel

# requirements.txt kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip show requests urllib3 yt-dlp websockets  # ← build logunda sürüm kontrolü

# Tüm proje dosyalarını kopyala (app/ klasörü dahil)
COPY . .

# PYTHONPATH ekle (app modülünü bulması için – en kritik kısım)
ENV PYTHONPATH=/vroxy

# Varsayılan komut (production için)
CMD ["python", "-u", "vroxy.py"]

# ====================
# Dev stage (geliştirme/test için ekstra bağımlılıklar)
# ====================
FROM base AS dev

# Geliştirme bağımlılıkları (flake8, pytest vs. varsa)
COPY requirements_dev.txt ./
RUN pip install --no-cache-dir -r requirements_dev.txt

# Dev modda aynı komut (daha detaylı log için -u flag'i korundu)
CMD ["python", "-u", "vroxy.py"]
