# WIP — droits par projet (branche `feat/project-rbac`)

Décision : `docs/decisions/0001-droits-par-projet.md`.

## État

- [x] Fork, clone, environnement (`uvx --from 'uv>=0.11.8' uv sync --frozen --all-groups`)
- [x] Squelette `label_studio/project_rbac/`
- [x] Modèle `ProjectRole` + migration
- [x] Visibilité (`RBACProjectMixin`, `for_user`, listes de projets)
- [x] Matrice des rôles (`ProjectRolePermission`)
- [x] API des membres `api/projects/<pk>/roles/`
- [x] Webhooks (filtrés sur les projets gérés)
- [ ] Vues hors matrice restantes : data_import (FileUploadAPI, UploadedFileResponse, DownloadStorageData), io_storages proxy, react_code_proxy, FSM
- [x] Tests de sécurité (33, contrôle négatif : 13 échecs sans RBAC)
- [ ] Suite amont : comparer à la base `79c00e68` (worktree `../label-studio-baseline`)
- [ ] Interface (lot suivant)

## Lancer les tests

```bash
cd label_studio
env -u VIRTUAL_ENV DJANGO_DB=sqlite ../.venv/bin/python -m pytest project_rbac -q -p no:cacheprovider
```

`uv` global en 0.7 : trop ancien pour ce `pyproject.toml` (`exclude-newer = "4 days"`).

## Points ouverts

- Les annotateurs voient les annotations des autres (comportement amont conservé).
- `/api/users` liste tous les membres de l'organisation.
- Déploiement : `SENTRY_DSN=` vide (sinon erreurs envoyées au Sentry de HumanSignal), Postgres, proxy HTTPS.
