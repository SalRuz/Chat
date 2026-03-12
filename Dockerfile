FROM node:22-alpine

WORKDIR /app

ENV DATA_DIR=/app/data

# Установка системных зависимостей для canvas и prismarine-viewer
RUN apk add --no-cache \
    build-base \
    python3 \
    cairo-dev \
    pango-dev \
    jpeg-dev \
    giflib-dev \
    librsvg-dev \
    mesa-dev \
    libx11

RUN mkdir -p /app/data && chmod 777 /app/data

COPY package*.json ./

RUN npm ci --omit=dev || npm install --omit=dev

COPY . .

EXPOSE 3000

CMD ["node", "bot.js"]
