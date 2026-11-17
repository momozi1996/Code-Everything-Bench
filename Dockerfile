# Pinned evaluation environment. Browser version is part of the benchmark
# contract: scrollWidth, font metrics and canvas rasterisation differ between
# Chromium releases and would otherwise make assertions non-reproducible.
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CEBENCH_BROWSER=chromium

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-liberation fonts-noto-cjk ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /cebench
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .
ENV PYTHONPATH=/cebench

# Default: validate the artifact without running any model.
CMD ["python3", "-m", "cebench.cli", "selftest"]
