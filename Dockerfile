# syntax=docker/dockerfile:1.4

FROM --platform=$BUILDPLATFORM python:3.10-alpine AS builder
EXPOSE 8000
WORKDIR /app 
COPY requirements.txt /app
RUN apk add --no-cache gcc musl-dev libffi-dev pkgconf mariadb-dev mariadb-connector-c-dev g++ python3-dev
RUN pip3 install -r requirements.txt --no-cache-dir
COPY . /app 

# Copy crontab file to the cron.d directory
COPY crontab /etc/cron.d/crontab
RUN chmod 777 /etc/cron.d/crontab
RUN crontab /etc/cron.d/crontab
RUN mkdir /logs

FROM builder as dev-envs
RUN <<EOF
apk update
apk add git
EOF

RUN <<EOF
addgroup -S docker
adduser -S --shell /bin/bash --ingroup docker vscode
EOF
# install Docker tools (cli, buildx, compose)
COPY --from=gloursdocker/docker / /
RUN python3 manage.py collectstatic --noinput
CMD ["uvicorn", "CPTBackend.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]