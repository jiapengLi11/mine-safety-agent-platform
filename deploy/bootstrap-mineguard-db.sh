#!/usr/bin/env bash
set -euo pipefail

container_name="${MYSQL_CONTAINER_NAME:-mysql8}"
redis_container_name="${REDIS_CONTAINER_NAME:-redis}"
app_dir="$HOME/apps/mineguard"
env_file="$app_dir/mineguard.local.env"

if ! docker inspect "$container_name" >/dev/null 2>&1; then
  echo "MySQL container '$container_name' was not found." >&2
  exit 1
fi

root_password="$({
  docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$container_name" \
    | sed -n 's/^MYSQL_ROOT_PASSWORD=//p' \
    | head -n 1
} || true)"

if [[ -z "$root_password" ]]; then
  echo "MYSQL_ROOT_PASSWORD is not available from the existing container configuration." >&2
  exit 1
fi

if ! docker inspect "$redis_container_name" >/dev/null 2>&1; then
  echo "Redis container '$redis_container_name' was not found." >&2
  exit 1
fi

redis_command="$(docker inspect --format '{{join .Config.Cmd " "}}' "$redis_container_name")"
redis_password="$(printf '%s' "$redis_command" | sed -nE 's/.*--requirepass[ =]+([^ ]+).*/\1/p')"
if [[ -z "$redis_password" ]]; then
  echo "Redis requirepass value is not available from the existing container configuration." >&2
  exit 1
fi

if [[ "$redis_password" == *'$'* || "$redis_password" == *'%'* ]]; then
  echo "Redis password contains unsupported environment-file characters." >&2
  exit 1
fi

mkdir -p "$app_dir"
umask 077
app_password="$(openssl rand -hex 24)"

docker exec -i -e MYSQL_PWD="$root_password" "$container_name" mysql -uroot <<SQL
CREATE DATABASE IF NOT EXISTS mineguard CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'mineguard'@'%' IDENTIFIED BY '${app_password}';
ALTER USER 'mineguard'@'%' IDENTIFIED BY '${app_password}';
GRANT ALL PRIVILEGES ON mineguard.* TO 'mineguard'@'%';
FLUSH PRIVILEGES;
SQL

cat >"$env_file" <<ENV
MINEGUARD_DB_URL=jdbc:mysql://127.0.0.1:3306/mineguard?useUnicode=true&characterEncoding=utf8&serverTimezone=UTC
MINEGUARD_DB_USER=mineguard
MINEGUARD_DB_PASSWORD=${app_password}
MINEGUARD_REDIS_HOST=127.0.0.1
MINEGUARD_REDIS_PORT=6379
MINEGUARD_REDIS_PASSWORD=${redis_password}
MINEGUARD_REDIS_KEY_PREFIX=mineguard:
MINEGUARD_KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092
MINEGUARD_KAFKA_CONSUMER_GROUP=mineguard-safety-core-v1
MINEGUARD_TOPIC_DETECTION_FRAME=mineguard.vision.detection.frame.v1
MINEGUARD_TOPIC_ALERT_CREATED=mineguard.safety.alert.created.v1
MINEGUARD_HTTP_PORT=18080
ENV

chmod 600 "$env_file"
unset root_password app_password redis_command redis_password
echo "MineGuard database and protected environment file are ready. No secret was printed."
