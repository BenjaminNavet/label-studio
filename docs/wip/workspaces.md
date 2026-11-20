# WIP — workspaces (branche `feat/project-rbac`)

Décision : `docs/decisions/0004-workspaces.md`. Socle : `docs/wip/droits-par-projet.md` (tests, déploiement).

## État

- [x] Lot 1 — cadrage : ADR 0004, cette note, squelette (modèles, routes, tests désactivés)
- [ ] Lot 2 — dossiers : CRUD des workspaces, rattachement d'un projet, filtre `?workspace=`
- [ ] Lot 3 — droits : rôle effectif dans `access.py`, API des membres, tests de sécurité
- [ ] Lot 4 — interface : barre latérale des workspaces sur la page Projects
- [ ] Lot 5 — interface : sélecteur « Workspace » (création, réglages généraux), fenêtre du workspace
- [ ] Lot 6 — intégration : image Docker, scénario d'API, interface en headless, suite amont

Prochaine étape : lot 2.

## Contrat d'API

```
GET    /api/workspaces/                       -> [{id, title, color, created_by, is_owner, role, can_manage,
                                                   can_delete, project_count, created_at, updated_at}]
POST   /api/workspaces/                       {title, color?} -> 201
GET    /api/workspaces/<pk>/                  -> un workspace ; 404 s'il est invisible
PATCH  /api/workspaces/<pk>/                  {title?, color?}             managers
DELETE /api/workspaces/<pk>/                  -> 204                       propriétaire ; projets détachés
GET    /api/workspaces/<pk>/roles/            -> [{user, email, first_name, last_name, role, is_owner,
                                                   created_at, updated_at}]              managers
POST   /api/workspaces/<pk>/roles/            {email | user, role} -> 201 (créé) ou 200 (remplacé)
DELETE /api/workspaces/<pk>/roles/<user_pk>/  -> 204 ; 400 pour le propriétaire
GET    /api/projects/<pk>/workspace/          -> {workspace: {id, title, color} | null, can_change}
PUT    /api/projects/<pk>/workspace/          {workspace: id | null} -> idem
GET    /api/projects/?workspace=<id>|none     filtre de la liste des projets
GET    /api/projects/<pk>/roles/              chaque ligne gagne `workspace_role` ; `role` vaut null pour
                                              un membre seulement hérité
```

`role` d'un workspace : rôle du demandeur dans ce workspace (null pour un administrateur non membre).
L'administrateur a tous les droits partout.

## Points ouverts

(aucun pour l'instant)
