# WIP — workspaces (branche `feat/project-rbac`)

Décision : `docs/decisions/0004-workspaces.md`. Socle : `docs/wip/droits-par-projet.md` (tests, déploiement).

## État

Chantier terminé le 2026-11-20, non poussé, non déployé.

- [x] Lot 1 — cadrage : ADR 0004, cette note, squelette (modèles, routes, tests désactivés)
- [x] Lot 2 — dossiers : CRUD des workspaces (`workspaces.py`), rattachement d'un projet, filtre
      `?workspace=` (`filters.py`, branché dans `ProjectFilterSet`)
- [x] Lot 3 — droits : rôle effectif dans `access.py` (`get_role`, `in_user_projects`, `_teammates`,
      `managed_by`, règles `can_*_workspace` / `can_*_project`), API des membres, 33 tests
      (`tests/test_workspaces.py`) ; `project_rbac` : 123 tests
- [x] Lot 4 — interface : barre latérale des workspaces sur la page Projects
      (`pages/Projects/WorkspacesSidebar.jsx`, `WorkspaceModal.jsx`)
- [x] Lot 5 — interface : sélecteur « Workspace » à la création et dans les réglages généraux
      (`components/WorkspaceSelect/`), membres partagés entre projets et workspaces
      (`components/RoleMembers/`)
- [x] Lot 6 — intégration : image `label-studio-rbac:workspaces`, scénario de bout en bout 29/29
      (`deploy/rbac-localhost/check_workspaces.py`, interface en headless et contrôles par l'API),
      suite amont : 27 échecs, exactement ceux de `echecs-attendus-suite-amont.txt`

Prochaine étape : déployer. La migration `project_rbac.0003_workspaces` ne crée que des tables ; aucun
workspace n'existe au départ, les accès actuels ne changent pas.

Points d'accroche ajoutés dans le code amont (à surveiller lors des fusions depuis `upstream/develop`) :
`projects/api.py` (`ProjectFilterSet.workspace`), `core/all_urls.json` (23 routes : 5 d'API, 18 de l'admin
Django), `config/ApiConfig.js`, `pages/Projects/Projects.jsx` et `Projects.prefix.css`,
`pages/CreateProject/CreateProject.jsx`, `pages/Settings/GeneralSettings.jsx`.

## Rejouer la vérification

```bash
# suite amont sans les fichiers tavern (ils se lancent depuis la racine, voir droits-par-projet.md)
cd label_studio && env -u VIRTUAL_ENV DJANGO_DB=sqlite ../.venv/bin/python -m pytest -q -p no:cacheprovider \
    -n 6 --tb=no -rfE --ignore-glob='*.tavern.yml'

# bout en bout, sur une pile neuve et isolée (autre nom de projet compose, autre port, volumes à part)
docker build -t label-studio-rbac:workspaces .
docker compose -p ws-essai --env-file <fichier .env d'essai> -f deploy/rbac-localhost/docker-compose.yml up -d
BASE=http://localhost:<port> uv run --no-project --with playwright python deploy/rbac-localhost/check_workspaces.py
docker compose -p ws-essai --env-file <fichier .env d'essai> -f deploy/rbac-localhost/docker-compose.yml down -v
```

Sans navigateur Playwright à la bonne version : `HEADLESS_SHELL=<chemin de chrome-headless-shell>` (celui de
`~/Library/Caches/ms-playwright/chromium_headless_shell-*/` convient), aucune fenêtre ne s'ouvre.

## Pièges rencontrés

- La couche d'API du frontend (`libs/core/.../api-proxy`) n'envoie un corps JSON qu'en `POST`, `PATCH` et
  `DELETE` : un `PUT` part sans corps. Le rattachement est donc un `PATCH`.
- Le `Select` de `@humansignal/ui` garde sa propre valeur et ne se resynchronise que si la prop `value`
  change : après un refus ou une annulation, il faut le remonter (`key`), comme dans `GeneralSettings.jsx`.
- La boîte `confirm` s'insère avant la fenêtre qui l'ouvre dans le DOM : un test qui prend « le dernier »
  bouton du même nom clique sous le voile.

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
PATCH  /api/projects/<pk>/workspace/          {workspace: id | null} -> idem
GET    /api/projects/?workspace=<id>|none     filtre de la liste des projets
GET    /api/projects/<pk>/roles/              chaque ligne gagne `workspace_role` ; `role` vaut null pour
                                              un membre seulement hérité
```

`role` d'un workspace : rôle du demandeur dans ce workspace (null pour un administrateur non membre).
L'administrateur a tous les droits partout.

## Points ouverts

- Les cartes de projet n'affichent pas le nom du workspace : la liste des projets ne le renvoie pas (il
  faudrait toucher au sérialiseur amont ou faire un appel par carte).
- Pas de transfert de propriété d'un workspace dans l'interface : modifier `created_by` dans l'admin
  Django et donner le rôle manager au nouveau propriétaire.
- Un membre seulement hérité ne se retire pas depuis le projet (404 voulu) : l'interface le montre en
  lecture seule, sans lien direct vers les réglages du workspace.
- Interface en anglais, comme le reste de l'application.
