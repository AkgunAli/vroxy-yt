# ====================
# Tek stage (Render için basit tutmak en iyisi – multi-stage gerek yok)
# ====================
FROM python:3.10.6-slim

# Çalışma dizini
WORKDIR /vroxy

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pip'i güncelle
RUN pip install --upgrade pip setuptools wheel

# requirements.txt kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip show requests urllib3 yt-dlp websockets

# Tüm proje dosyalarını kopyala (app/ dahil)
COPY . .

# PYTHONPATH'i mutlaka ekle (app paketini bulması için)
ENV PYTHONPATH=/vroxy

# Uygulamayı başlat
CMD ["python", "-u", "vroxy.py"]
