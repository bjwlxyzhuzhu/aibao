FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ torch torchaudio --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ funasr modelscope fastapi uvicorn python-multipart
WORKDIR /srv
COPY asr/server.py .
ENV MODELSCOPE_CACHE=/models
EXPOSE 9000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "9000"]
