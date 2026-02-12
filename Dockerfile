FROM python:3.10.6-slim

# Render'ın sevdiği standart dizin
WORKDIR /app

# Pip güncelle
RUN pip install --upgrade pip setuptools wheel

# requirements.txt kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tüm dosyaları kopyala (app/ dahil)
COPY . .

# PYTHONPATH ekle (app modülü için)
ENV PYTHONPATH=/app

# Port belirt
EXPOSE 8008

# Komut (göreceli yol – WORKDIR'e göre)
CMD ["python", "-u", "vroxy.py"]
