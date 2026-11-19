# Déploiement serveur (fork Label Studio, rôles par projet)

Image du fork derrière Caddy (HTTPS), avec Postgres et sauvegardes. Seuls les ports 80 et 443 sont publiés ; Postgres et Label Studio ne sont joignables que par le réseau Docker.

## Prérequis

- Docker Engine avec le plugin Compose v2.
- Un nom d'hôte qui pointe vers le serveur (DNS interne ou public).
- Ports 80 et 443 (TCP, et 443/UDP pour HTTP/3) ouverts vers le serveur.

## Récupérer l'image

Construction sur le serveur, depuis la racine du dépôt :

```bash
docker build -t label-studio-rbac:local .
```

Ou construction ailleurs puis transfert :

```bash
docker save label-studio-rbac:local | gzip | ssh user@serveur 'gunzip | docker load'
```

## Configuration

```bash
cd deploy/server
cp .env.example .env
chmod 600 .env
$EDITOR .env   # domaine, mots de passe, mode TLS
```

Variables obligatoires : `LABEL_STUDIO_DOMAIN`, `POSTGRES_PASSWORD`, `LABEL_STUDIO_USERNAME`, `LABEL_STUDIO_PASSWORD`. Compose refuse de démarrer si l'une manque.

## Premier démarrage

```bash
docker compose --env-file .env up -d
docker compose --env-file .env logs -f label-studio   # migrations, puis serveur démarré
```

Ouvrir `https://<LABEL_STUDIO_DOMAIN>` et se connecter avec `LABEL_STUDIO_USERNAME` / `LABEL_STUDIO_PASSWORD` : ce compte est propriétaire de l'organisation, donc administrateur de tous les projets. Les autres comptes se créent depuis l'interface (Organization > Accounts) ; on invite ensuite les personnes dans un projet depuis sa page Settings > Members. L'inscription libre est fermée.

Le mot de passe d'un compte est généré par le serveur et affiché une seule fois à l'administrateur, qui le transmet. L'édition communautaire n'a pas d'écran de changement de mot de passe : pour en changer, l'administrateur utilise « Reset password ».

## Mode TLS (`CADDY_TLS` dans `.env`)

- `internal` (défaut) : Caddy signe avec sa propre autorité, pour un nom d'hôte interne. Les navigateurs affichent un avertissement tant que cette autorité n'est pas approuvée ; son certificat racine se récupère avec `docker compose --env-file .env cp caddy:/data/caddy/pki/authorities/local/root.crt .`.
- Une adresse e-mail (ex. `admin@example.org`) : Let's Encrypt. Exige un nom DNS public et les ports 80/443 joignables depuis Internet.
- `/certs/fullchain.pem /certs/privkey.pem` : certificat fourni par la DSI. Déposer les deux fichiers dans `deploy/server/certs/` (monté en lecture seule sur `/certs`), puis `docker compose --env-file .env up -d`.

## Sauvegardes

`backup.sh` écrit dans `BACKUP_DIR` (défaut `./backups`, relatif à ce dossier) un dump `postgres-<date>.sql.gz` et une archive `lsdata-<date>.tar.gz` (volume de données), puis supprime ceux de plus de `BACKUP_RETENTION_DAYS` jours (défaut 14). Le script lit `.env` lui-même.

```bash
./backup.sh
```

Cron (tous les jours à 02:30) :

```cron
30 2 * * * /opt/label-studio/deploy/server/backup.sh >> /var/log/ls-backup.log 2>&1
```

Copier régulièrement `backups/` hors du serveur.

### Restauration

```bash
cd deploy/server
docker compose --env-file .env stop label-studio
# Base : repartir d'une base vide
docker compose --env-file .env exec -T postgres psql -U labelstudio -d postgres \
  -c 'DROP DATABASE labelstudio;' -c 'CREATE DATABASE labelstudio OWNER labelstudio;'
gunzip -c backups/postgres-AAAAMMJJ-HHMMSS.sql.gz \
  | docker compose --env-file .env exec -T postgres psql -U labelstudio -d labelstudio
# Données (fichiers téléversés, etc.)
docker compose --env-file .env run --rm --no-deps -T --entrypoint sh label-studio \
  -c 'tar -C /label-studio/data -xzf -' < backups/lsdata-AAAAMMJJ-HHMMSS.tar.gz
docker compose --env-file .env up -d
```

## Mise à jour

```bash
git pull
docker build -t label-studio-rbac:local .   # ou docker load d'une image transférée
cd deploy/server
./backup.sh
docker compose --env-file .env up -d
```

Les migrations s'exécutent au démarrage du conteneur `label-studio`.

## Sécurité

- Inscription fermée (`LABEL_STUDIO_DISABLE_SIGNUP_WITHOUT_LINK`) ; les comptes sont créés par l'administrateur.
- Pare-feu : n'autoriser que 80 et 443 (plus SSH) en entrée.
- `.env` en mode 600, jamais commité (ignoré par `deploy/server/.gitignore`, comme `certs/*.pem` et `backups/`).
- Sentry et collecte d'analytique désactivés.
