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

- [x] Lot 1 — propriétaire (ADR 0002) : création par tout membre, rôle manager automatique (signal
      `post_save`), suppression réservée au propriétaire, invitation par e-mail, migration de données 0002
- [x] Lot 2 — vues hors matrice : `FileUploadAPI` (aucun contrôle d'objet en amont) passe par la matrice ;
      FSM : `get_permission_required` pris en compte, projet déduit de `<entity_name>/<entity_id>`.
      Vérifiées et déjà couvertes par `has_permission` : `UploadedFileResponse`, `DownloadStorageData`,
      proxy `io_storages`, `react_code_proxy`, `localfiles_data`
- [x] Lot 3 — comptes (ADR 0003) : API `/api/rbac/accounts/`, `/api/rbac/me/`, permissions d'organisation
      fermées aux membres, listes d'utilisateurs filtrées (`visible_users`, `visible_members`)
- [x] Lot 4 — interface : `pages/Settings/MembersSettings/` (réglages de projet > Members)
- [x] Lot 5 — interface : `pages/Organization/AccountsPage/` (Organization > Accounts, administrateurs) ;
      bouton « Add Members » masqué aux autres
- [x] Lot 6 — déploiement serveur : `deploy/server/` (Caddy HTTPS, Postgres, `backup.sh`, README)
- [x] Intégration (2026-11-20) : image construite (`label-studio-rbac:next`), essais de bout en bout sur
      la pile locale puis sur une copie de `deploy/server/` en HTTPS (Caddy, port local) :
      scénario d'API 36/36, interface en Chrome headless 19/19, `backup.sh` puis restauration du README
- [x] Suite amont : 27 échecs, tous dans `echecs-attendus-suite-amont.txt` (un test repasse, deux
      s'ajoutent : `PATCH` d'organisation par un membre désormais refusé en 403 au lieu d'ignoré en 200)

Points d'accroche dans le code amont (à surveiller lors des fusions depuis `upstream/develop`) :
`core/settings/base.py`, `core/urls.py`, `projects/models.py` (`for_user`), `projects/api.py`,
`webhooks/api.py`, `data_import/api.py` (`FileUploadAPI.permission_required`), `users/api.py`
(`UserAPI.get_queryset`), `organizations/api.py` (`OrganizationMemberListAPI.filter_queryset`),
`web/apps/labelstudio/src/config/ApiConfig.js`, `pages/Settings/index.jsx`, `pages/Organization/index.jsx`,
`pages/Organization/PeoplePage/PeoplePage.jsx`.

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

`project_rbac` : 90 tests. Contrôle négatif : sur le code d'avant le chantier du 2026-11-19, 23 des
nouveaux tests échouent et 21 sont en erreur.

Suite amont complète (environ 5 min avec `-n 6`). Les tests tavern se lancent depuis la racine du dépôt,
sinon `shared_stages.yml` est introuvable :

```bash
cd label_studio && env -u VIRTUAL_ENV DJANGO_DB=sqlite ../.venv/bin/python -m pytest -q -p no:cacheprovider -n 6 --tb=no -rfE
cd .. && env -u VIRTUAL_ENV DJANGO_DB=sqlite .venv/bin/python -m pytest $(find label_studio -name "*.tavern.yml") -q -p no:cacheprovider -n 6 --tb=no -rfE
```

`uv` global en 0.7 : trop ancien pour ce `pyproject.toml` (`exclude-newer = "4 days"`).
Frontend : ni `bun` ni `node_modules` sur ce poste ; la compilation se vérifie par `docker build`
(première construction longue : `opencv` compilé depuis les sources, ensuite en cache).

Essai dans un navigateur : ouvrir l'interface sur le nom d'hôte de `LABEL_STUDIO_HOST` (`localhost`, pas
`127.0.0.1`), sinon les appels d'API partent vers une autre origine, sans cookie, et tout répond 401.
Une page de l'application ouverte directement par son URL a besoin d'une route côté serveur
(`project_rbac/urls.py` pour `/organization/accounts` ; `/projects/<pk>/settings/<page>` existe en amont).

## Points ouverts

- Les annotateurs voient les annotations des autres dans un même projet (comportement amont conservé).
- Pas d'écran de changement de mot de passe dans l'édition communautaire : le mot de passe est celui que
  l'administrateur génère (« Reset password » pour en changer).
- Pas de transfert de propriété d'un projet dans l'interface : modifier `created_by` dans l'admin Django
  et donner le rôle manager au nouveau propriétaire.
- L'assistant de création crée un projet brouillon à chaque ouverture (comportement amont) : ils comptent
  dans la colonne « Projects » de la page Accounts.
- `deploy/server/` : modes TLS « e-mail » (Let's Encrypt) et « fichiers de certificat » validés par
  `caddy validate` seulement ; seul le mode `internal` a tourné.
- Interface en anglais, comme le reste de l'application.
