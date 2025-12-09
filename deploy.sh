#!/bin/bash
set -e

docker pull ghcr.nju.edu.cn/nyush-cpt/cpt-be-2024@$IMAGE_SHA

echo "Stopping old containers if they exist..."

# 停掉老的单一后端容器（兼容历史）
if [ "$(docker ps -q -f name=cpt-be$)" ]; then
    docker stop cpt-be || true
    docker rm cpt-be || true
else
    echo "Container cpt-be does not exist."
fi

# 停掉新的 api/admin 容器（如果之前已经有）
if [ "$(docker ps -q -f name=cpt-be-api$)" ]; then
    docker stop cpt-be-api || true
    docker rm cpt-be-api || true
fi

if [ "$(docker ps -q -f name=cpt-be-admin$)" ]; then
    docker stop cpt-be-admin || true
    docker rm cpt-be-admin || true
fi

# 停掉 crontab 容器
if [ "$(docker ps -q -f name=cpt-be-crontab$)" ]; then
    docker stop cpt-be-crontab || true
    docker rm cpt-be-crontab || true
else
    echo "Container cpt-be-crontab does not exist."
fi

sleep 3

echo "Starting API container (cpt-be-api)..."

docker run \
  --restart always \
  --memory=900m \
  --cpus="1.4" \
  -v /home/ubuntu/staticfiles:/app/staticfiles \
  -e "CORS_ALLOWED_ORIGINS=$CORS_ALLOWED_ORIGINS" \
  -e "DB_HOST=$DB_HOST" \
  -e "DB_NAME=$DB_NAME" \
  -e "DB_PORT=$DB_PORT" \
  -e "DB_USER=$DB_USER" \
  -e "DB_PASSWORD=$DB_PASSWORD" \
  -e "AES_KEY=$AES_KEY" \
  -e "WEB_URL=$WEB_URL" \
  -e "BLUED_API=$BLUED_API" \
  -e "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" \
  -e "QR_JWT_SECRET=$QR_JWT_SECRET" \
  -d --name cpt-be-api -p 8000:8000 \
  ghcr.nju.edu.cn/nyush-cpt/cpt-be-2024@$IMAGE_SHA \
  uvicorn CPTBackend.asgi:application --host 0.0.0.0 --port 8000 --workers 2

docker exec cpt-be-api python manage.py collectstatic --noinput


# Admin 容器：只给你和 RA/INFO 用，1 个 worker 就够
# 这里不覆盖 CMD，直接用 Dockerfile 里的 --workers 1
docker run \
  --restart always \
  --memory=500m \
  --cpus="0.6" \
  -v /home/ubuntu/staticfiles:/app/staticfiles \
  -e "CORS_ALLOWED_ORIGINS=$CORS_ALLOWED_ORIGINS" \
  -e "DB_HOST=$DB_HOST" \
  -e "DB_NAME=$DB_NAME" \
  -e "DB_PORT=$DB_PORT" \
  -e "DB_USER=$DB_USER" \
  -e "DB_PASSWORD=$DB_PASSWORD" \
  -e "AES_KEY=$AES_KEY" \
  -e "WEB_URL=$WEB_URL" \
  -e "BLUED_API=$BLUED_API" \
  -e "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" \
  -e "QR_JWT_SECRET=$QR_JWT_SECRET" \
  -d --name cpt-be-admin -p 8001:8000 \
  ghcr.nju.edu.cn/nyush-cpt/cpt-be-2024@$IMAGE_SHA

echo "Starting crontab container (cpt-be-crontab)..."

docker run \
  --restart always \
  --memory=200m \
  --cpus="0.3" \
  -e "CORS_ALLOWED_ORIGINS=$CORS_ALLOWED_ORIGINS" \
  -e "DB_HOST=$DB_HOST" \
  -e "DB_NAME=$DB_NAME" \
  -e "DB_PORT=$DB_PORT" \
  -e "DB_USER=$DB_USER" \
  -e "DB_PASSWORD=$DB_PASSWORD" \
  -e "AES_KEY=$AES_KEY" \
  -e "WEB_URL=$WEB_URL" \
  -e "BLUED_API=$BLUED_API" \
  -e "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" \
  -d --name cpt-be-crontab \
  ghcr.nju.edu.cn/nyush-cpt/cpt-be-2024@$IMAGE_SHA \
  /usr/sbin/crond -f

echo "Pruning unused docker resources..."
docker system prune -f

docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.RunningFor}}"