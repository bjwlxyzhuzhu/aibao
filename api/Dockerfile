FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libreoffice-writer-nogui fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY api/requirements.txt .
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --index-url ${PIP_INDEX_URL} -r requirements.txt
COPY api/ /app/
COPY assets/ /assets/
ENV DATA_DIR=/data ASSETS_DIR=/assets
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
