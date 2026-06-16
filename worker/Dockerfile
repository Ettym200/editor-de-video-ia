FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    unzip \
    chromium \
    chromium-driver \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Instala bun
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# Instala tsx globalmente (necessário para build do core)
RUN npm install -g tsx

# Clona HyperFrames
RUN git clone --depth=1 https://github.com/heygen-com/hyperframes /app/hyperframes

WORKDIR /app/hyperframes

# Instala todas as dependências do monorepo
RUN bun install

# Builda core primeiro (gera runtime-inline)
RUN cd packages/core && bun run build:hyperframes-runtime && npx tsc --noEmit 2>/dev/null || bun run build 2>/dev/null || true

# Builda CLI
RUN cd packages/cli && bun run build 2>/dev/null || true

# Cria wrapper
RUN echo '#!/bin/sh' > /usr/local/bin/hyperframes \
    && echo 'exec node /app/hyperframes/packages/cli/dist/cli.js "$@"' >> /usr/local/bin/hyperframes \
    && chmod +x /usr/local/bin/hyperframes

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir setuptools wheel
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir openai-whisper --no-build-isolation
RUN pip install --no-cache-dir redis anthropic python-dotenv httpx requests

COPY . .

ENV HYPERFRAMES_BIN="hyperframes"

CMD ["python", "main.py"]
