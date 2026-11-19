# WIP — droits par projet (branche `feat/project-rbac`)

Décisions : `docs/decisions/0001-droits-par-projet.md`, `0002-proprietaire-et-creation-par-les-membres.md`,
`0003-comptes-geres-par-les-administrateurs.md`.

## État

- [x] Fork, clone, environnement (`uvx --from 'uv>=0.11.8' uv sync --frozen --all-groups`)
- [x] Squelette `label_studio/project_rbac/`
- [x] Modèle `ProjectRole` + migration
- [x] Visibilité (`RBACProjectMixin`, `for_user`, listes de projets)
- [x] Matrice des rôles (`ProjectRolePermission`)
- [x] API des membres `api/projects/<pk>/roles/`
- [x] Webhooks (filtrés sur les projets gérés)
- [x] Tests de sécurité, suite amont (échecs attendus dans `echecs-attendus-suite-amont.txt`)
- [x] Déploiement local : `deploy/rbac-localhost/` (image du fork + Postgres, 127.0.0.1)

### Chantier du 2026-11-19 : propriétaire, comptes, interface, serveur

Squelette commité (ADR 0002 et 0003, routes, tests désactivés, points d'API du frontend).

- [ ] Lot 1 — propriétaire (ADR 0002) : création par tout membre, rôle manager automatique, suppression
      réservée au propriétaire, invitation par e-mail, migration de données
- [ ] Lot 2 — vues hors matrice : `FileUploadAPI` (aucun contrôle d'objet en amont), FSM
      (`get_permission_required` ignoré). Vérifiées et déjà couvertes par `has_permission` :
      `UploadedFileResponse`, `DownloadStorageData`, proxy `io_storages`, `react_code_proxy`, `localfiles_data`
- [ ] Lot 3 — comptes (ADR 0003) : API `/api/rbac/accounts/`, `/api/rbac/me/`, verrouillage des permissions
      d'organisation, listes d'utilisateurs filtrées
- [ ] Lot 4 — interface : page « Members » des réglages de projet
- [ ] Lot 5 — interface : page « Accounts » de l'organisation (administrateurs)
- [ ] Lot 6 — déploiement serveur : `deploy/server/` (proxy HTTPS, sauvegardes)
- [ ] Intégration : image Docker, essai de bout en bout, suite amont

## Contrat d'API (lots 1 et 3)

```
GET    /api/projects/<pk>/roles/            -> [{user, email, first_name, last_name, role, is_owner, created_at, updated_at}]
POST   /api/projects/<pk>/roles/            {email | user, role}  -> 201 (créé) ou 200 (rôle remplacé)
DELETE /api/projects/<pk>/roles/<user_pk>/  -> 204 ; 400 pour le propriétaire
GET    /api/rbac/me/                        -> {is_admin}
GET    /api/rbac/accounts/                  -> [{id, email, first_name, last_name, is_active, is_admin, is_owner,
                                                 last_activity, date_joined, project_count}]
POST   /api/rbac/accounts/                  {email, first_name?, last_name?, is_admin?} -> 201 {…, password}
PATCH  /api/rbac/accounts/<pk>/             {email?, first_name?, last_name?, is_active?, is_admin?}
POST   /api/rbac/accounts/<pk>/reset-password/  -> {password}
```

Rôles : `manager`, `reviewer`, `annotator`. Erreurs de validation : 400 `{champ: [message]}`.

## Lancer les tests

```bash
cd label_studio
env -u VIRTUAL_ENV DJANGO_DB=sqlite ../.venv/bin/python -m pytest project_rbac -q -p no:cacheprovider
```

`uv` global en 0.7 : trop ancien pour ce `pyproject.toml` (`exclude-newer = "4 days"`).
Frontend : ni `bun` ni `node_modules` sur ce poste ; la compilation se vérifie par `docker build -t label-studio-rbac:local .`.

## Points ouverts

- Les annotateurs voient les annotations des autres dans un même projet (comportement amont conservé).
- Pas d'écran de changement de mot de passe dans l'édition communautaire : le mot de passe est celui que
  l'administrateur génère.
- Pas de transfert de propriété d'un projet dans l'interface (admin Django).
