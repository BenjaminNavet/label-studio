#!/usr/bin/env bash
# Back up Postgres (pg_dump) and the Label Studio data volume. Safe to run from cron.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose_file="${script_dir}/docker-compose.yml"
env_file="${script_dir}/.env"

# Read one variable from .env without evaluating the file: a value may hold a space
# (CADDY_TLS=/certs/fullchain.pem /certs/privkey.pem), which `source` would run as a command.
read_env() {
    local name="$1" default="$2" value=""
    if [[ -f "${env_file}" ]]; then
        value="$(grep -E "^${name}=" "${env_file}" | tail -n 1 | cut -d= -f2-)" || true
    fi
    printf '%s' "${value:-${default}}"
}

backup_dir="${BACKUP_DIR:-$(read_env BACKUP_DIR ./backups)}"
[[ "${backup_dir}" = /* ]] || backup_dir="${script_dir}/${backup_dir}"
retention_days="${BACKUP_RETENTION_DAYS:-$(read_env BACKUP_RETENTION_DAYS 14)}"
timestamp="$(date +%Y%m%d-%H%M%S)"

compose=(docker compose -f "${compose_file}" --env-file "${env_file}")

mkdir -p "${backup_dir}"
umask 077

echo "Dumping Postgres..."
"${compose[@]}" exec -T postgres pg_dump -U labelstudio -d labelstudio \
    | gzip > "${backup_dir}/postgres-${timestamp}.sql.gz"

echo "Archiving Label Studio data..."
"${compose[@]}" exec -T label-studio tar -C /label-studio/data -czf - . \
    > "${backup_dir}/lsdata-${timestamp}.tar.gz"

echo "Deleting backups older than ${retention_days} days..."
find "${backup_dir}" -maxdepth 1 -type f \
    \( -name 'postgres-*.sql.gz' -o -name 'lsdata-*.tar.gz' \) \
    -mtime +"${retention_days}" -delete

echo "Backup done: ${backup_dir} (${timestamp})"
