#!/usr/bin/env bash
# Back up Postgres (pg_dump) and the Label Studio data volume. Safe to run from cron.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose_file="${script_dir}/docker-compose.yml"
env_file="${script_dir}/.env"

# Load BACKUP_* from .env unless already set in the environment.
if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${env_file}"
    set +a
fi

backup_dir="${BACKUP_DIR:-./backups}"
[[ "${backup_dir}" = /* ]] || backup_dir="${script_dir}/${backup_dir}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
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
