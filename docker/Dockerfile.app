FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        default-mysql-client \
        cdo \
        gdal-bin \
        htop \
        vim \
        git \
        build-essential \
        g++ \
        zlib1g-dev \
        libsqlite3-dev \
    && git clone --depth 1 https://github.com/felt/tippecanoe.git /tmp/tippecanoe \
    && make -C /tmp/tippecanoe -j"$(nproc)" \
    && make -C /tmp/tippecanoe install \
    && rm -rf /tmp/tippecanoe \
    && apt-get purge -y git build-essential g++ \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install -e .

RUN mkdir -p /descargas /logs /output /output/tiles /output/tmp

COPY docker/entrypoint.sh /entrypoint.sh
COPY scripts ./scripts
RUN chmod +x /entrypoint.sh && find scripts -type f -name '*.sh' -exec chmod +x {} +

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]
