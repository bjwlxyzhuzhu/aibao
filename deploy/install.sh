#!/usr/bin/env bash
# 部署第一步：检测服务器配置（无 GPU、纯 CPU 设计），再启动 Docker Compose
set -e
cores=$(nproc); mem=$(free -g | awk '/Mem:/{print $2}'); disk=$(df -BG --output=avail . | tail -1 | tr -dc 0-9)
dver=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 0)
echo "CPU ${cores} 核 · 内存 ${mem}GB · 可用磁盘 ${disk}GB · Docker ${dver}"
low=0
[ "$cores" -lt 4 ] && low=1; [ "$mem" -lt 8 ] && low=1; [ "$disk" -lt 50 ] && low=1
[ "${dver%%.*}" -lt 24 ] && { echo "需要 Docker 24 以上"; exit 1; }
[ -f .env ] || { cp .env.example .env; echo "已生成 .env，请先填写密钥后重新运行"; exit 1; }
if [ "$low" = 1 ]; then
  echo "低于最低档（4 核 / 8GB / 50GB）：语音识别降级为排队转写，其他功能不受影响"
  docker compose up -d --build db api web
else
  docker compose up -d --build
fi
echo "完成：访问 http://服务器:8080 ，由现有 HTTPS Nginx 反代到该端口"
