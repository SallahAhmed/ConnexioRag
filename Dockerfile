FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Note: Connexios uses "Requirements.txt" with a capital R
COPY src/Requirements.txt .
RUN pip install --no-cache-dir -r Requirements.txt

COPY . .

RUN chmod +x start.sh

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

EXPOSE 7860

CMD ["./start.sh"]
