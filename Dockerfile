FROM python:3.10.6-slim

WORKDIR /app

RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# PYTHONPATH'i /app yap
ENV PYTHONPATH=/app

# Port belirt
EXPOSE 8008

CMD ["python", "-u", "vroxy.py"]
