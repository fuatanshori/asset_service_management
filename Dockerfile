# ========== Stage 1: build Tailwind CSS pakai Node ==========
FROM node:20-slim AS tailwind-builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build:css:prod


# ========== Stage 2: Python/Django (image final) ==========
FROM python:3.13-slim-bookworm
WORKDIR /app

# Copy requirements dulu biar layer pip install ke-cache selama
# requirements.txt gak berubah — build jadi jauh lebih cepat pas cuma
# ubah kode.
COPY requirements.txt .

RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        python3-dev \
        default-libmysqlclient-dev \
        build-essential \
        pkg-config \
        curl \
        tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Timpa output.css versi lama (kalau ke-commit) dengan hasil compile
# terbaru dari stage 1
COPY --from=tailwind-builder /app/static/assets/css/output.css ./static/assets/css/output.css