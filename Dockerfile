FROM python:3.10.6-slim

# Render'da standart /app dizini kullan
WORKDIR /app

# Sistem bağımlılıkları (gerekli değil ama güvenli)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pip güncelle
RUN pip install --upgrade pip setuptools wheel

# requirements.txt kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tüm dosyaları kopyala
COPY . .

# PYTHONPATH'i /app yap (app klasörü burada)
ENV PYTHONPATH=/app

# Port belirt (Render otomatik algılasın)
EXPOSE 8008

# Start komutu (göreceli yol – WORKDIR'e göre)
CMD ["python", "-u", "vroxy.py"]
