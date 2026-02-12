FROM python:3.10.6 as base

WORKDIR /vroxy
CMD ["python", "-u", "vroxy.py"]

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

FROM base as dev

COPY requirements_dev.txt ./
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip show requests urllib3 yt-dlp   # ← logda sürüm kontrolü yapar
