# WIP — droits par projet (branche `feat/project-rbac`)

Décision : `docs/decisions/0001-droits-par-projet.md`.

## État

- [x] Fork, clone, environnement (`uvx --from 'uv>=0.11.8' uv sync --frozen --all-groups`)
- [ ] Squelette `label_studio/project_rbac/`
- [ ] Modèle `ProjectRole` + migration
- [ ] Visibilité (`RBACProjectMixin`, `for_user`, listes de projets)
- [ ] Matrice des rôles (`ProjectRolePermission`)
- [ ] API des membres `api/projects/<pk>/roles/`
- [ ] Vues hors matrice (webhooks, data_import `IsAuthenticated`)
- [ ] Tests de sécurité + suite amont des apps touchées
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
