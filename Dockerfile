# ========== Stage 1: build Tailwind CSS pakai Node ==========
FROM node:20-slim AS tailwind-builder
WORKDIR /app
COPY . .
RUN npm install
RUN npm run build:css:prod


# ========== Stage 2: Python/Django (image final) ==========
FROM python:3.13-slim-bullseye
WORKDIR /app
COPY . .

RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y python3-dev \
    && apt-get install -y default-libmysqlclient-dev \
    && apt-get install -y build-essential \
    && apt-get install -y pkg-config \
    && apt-get install -y curl \
    && apt-get install -y tzdata \
    && pip install -r requirements.txt

# Timpa output.css versi lama (kalau ke-commit) dengan hasil compile terbaru dari stage 1
COPY --from=tailwind-builder /app/static/assets/css/output.css ./static/assets/css/output.css