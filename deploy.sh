#!/bin/bash

docker pull ghcr.nju.edu.cn/nyush-cpt/cpt-be-2024@$IMAGE_SHA

# Stop the current container
if [ "$(docker ps -q -f name=cpt-be)" ]; then
    docker stop cpt-be || true
    docker rm cpt-be || true
else
    echo "Container cpt-be does not exist. Creating a new one."
fi

# Stop crontab container
if [ "$(docker ps -q -f name=cpt-be-crontab)" ]; then
    docker stop cpt-be-crontab || true
    docker rm cpt-be-crontab || true
else
    echo "Container cpt-be-crontab does not exist. Creating a new one."
fi


sleep 3

# Start a new container with the latest image
docker run  \
  -e "CORS_ALLOWED_ORIGINS=$CORS_ALLOWED_ORIGINS" \
  -e "DB_HOST=$DB_HOST" \
  -e "DB_NAME=$DB_NAME" \
  -e "DB_PORT=$DB_PORT" \
  -e "DB_USER=$DB_USER" \
  -e "ALIYUN_ACCESS_KEY_ID=$ALIYUN_ACCESS_KEY_ID" \
  -e "ALIYUN_ACCESS_SECRET=$ALIYUN_ACCESS_SECRET" \
  -e "DB_PASSWORD=$DB_PASSWORD" \
  -e "ENCRYPTION_SALT=$ENCRYPTION_SALT" \
  -e "SECRET_KEY=$SECRET_KEY" \
  -e "AES_KEY=$AES_KEY" \
  -e "WEB_URL=$WEB_URL" \
  -e "BLUED_API=$BLUED_API" \
  -e "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" \
  -d --name cpt-be -p 8000:8000 ghcr.nju.edu.cn/nyush-cpt/cpt-be-2024@$IMAGE_SHA

echo "Running collectstatic..."
docker exec cpt-be python manage.py collectstatic --noinput

# Start a new crontab container with the latest image
docker run  \
  -e "CORS_ALLOWED_ORIGINS=$CORS_ALLOWED_ORIGINS" \
  -e "DB_HOST=$DB_HOST" \
  -e "DB_NAME=$DB_NAME" \
  -e "DB_PORT=$DB_PORT" \
  -e "DB_USER=$DB_USER" \
  -e "ALIYUN_ACCESS_KEY_ID=$ALIYUN_ACCESS_KEY_ID" \
  -e "ALIYUN_ACCESS_SECRET=$ALIYUN_ACCESS_SECRET" \
  -e "DB_PASSWORD=$DB_PASSWORD" \
  -e "ENCRYPTION_SALT=$ENCRYPTION_SALT" \
  -e "SECRET_KEY=$SECRET_KEY" \
  -e "AES_KEY=$AES_KEY" \
  -e "WEB_URL=$WEB_URL" \
  -e "BLUED_API=$BLUED_API" \
  -e "DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" \ 
  -d --name cpt-be-crontab ghcr.nju.edu.cn/nyush-cpt/cpt-be-2024@$IMAGE_SHA \
  /usr/sbin/crond -f


docker system prune -f