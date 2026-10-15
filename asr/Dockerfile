FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 libgomp1 && rm -rf /var/lib/apt/lists/*
ARG PIP_INDEX_URL=https://pypi.org/simple
# Keep matching CPU wheels; newer torchaudio releases remove APIs used by FunASR.
RUN pip install --no-cache-dir torch==2.8.0+cpu torchaudio==2.8.0+cpu --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir --index-url ${PIP_INDEX_URL} 'numpy<2' 'funasr<2' 'modelscope<2' \
      fastapi==0.115.6 uvicorn==0.32.1 python-multipart==0.0.19 httpx==0.28.1
WORKDIR /srv
COPY asr/server.py .
ENV MODELSCOPE_CACHE=/models
EXPOSE 9000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "9000"]
