# 0003 — Comptes gérés par les administrateurs

Date : 2026-11-19 · Statut : acceptée · Remplace la dernière puce du point 5 de l'ADR 0001

## Contexte

L'ADR 0001 laissait les permissions d'organisation (`organizations.*`,
`users.*`) au comportement amont. Dans l'édition communautaire elles sont
ouvertes à tout membre : créer un compte (`POST /api/users`), modifier le profil
d'un autre membre (`PATCH /api/users/<pk>`, `User.has_permission` ne regarde que
le demandeur), lire le lien d'invitation, lister tous les membres. Sur une
instance partagée par plusieurs équipes, la gestion des comptes doit revenir aux
administrateurs.

## Décision

1. Administrateur = superutilisateur ou propriétaire de l'organisation
   (`access.is_org_admin`, inchangé).
2. Une API d'administration des comptes dans `project_rbac`, réservée aux
   administrateurs :
   - `GET /api/rbac/accounts/` : liste des comptes de l'organisation ;
   - `POST /api/rbac/accounts/` : création, mot de passe généré par le serveur
     et renvoyé une seule fois ;
   - `PATCH /api/rbac/accounts/<pk>/` : nom, e-mail, `is_active`, `is_admin` ;
   - `POST /api/rbac/accounts/<pk>/reset-password/` : nouveau mot de passe
     généré, renvoyé une seule fois.
3. Pas de suppression de compte : on désactive (`is_active = False`). Les
   annotations restent attribuées, la connexion (session, jeton, JWT) est
   refusée.
4. Un administrateur ne peut ni se désactiver ni se retirer ses propres droits ;
   le propriétaire de l'organisation ne peut être ni désactivé ni rétrogradé.
5. Pour les autres membres, dans `ProjectRolePermission` :
   - `organizations.invite` : refusé ;
   - `organizations.change` : lecture seule (pas de création ni de suppression
     de compte, pas de retrait de membre, pas de réglage d'organisation) ;
   - modification d'un utilisateur : soi-même uniquement ;
   - listes d'utilisateurs (`/api/users`, membres de l'organisation) : filtrées
     aux personnes qui partagent au moins un projet avec le demandeur.
6. `GET /api/rbac/me/` renvoie `{"is_admin": bool}` pour que l'interface
   n'affiche la gestion des comptes qu'aux administrateurs. Le contrôle reste
   côté serveur.

## Conséquences

- L'inscription par lien d'invitation reste possible, mais seul
  l'administrateur peut lire ou renouveler le lien.
- L'administrateur connaît le mot de passe initial qu'il transmet. L'édition
  communautaire n'a pas d'écran de changement de mot de passe : point ouvert.
- Les tests amont qui font créer ou modifier un compte par un membre ordinaire
  échouent : comportement voulu, à ajouter à la liste des échecs attendus.
