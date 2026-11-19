# 0002 — Propriétaire de projet et création par les membres

Date : 2026-11-19 · Statut : acceptée · Remplace le point 4 de l'ADR 0001 pour la création et la suppression

## Contexte

Le besoin du labo : chacun accède à son propre travail, et au travail d'un autre
seulement si son propriétaire l'y invite. L'ADR 0001 réservait la création et la
suppression des projets à l'administrateur, qui devait ensuite nommer un
`manager` : il n'y avait pas de propriétaire.

L'interface amont crée un projet brouillon dès l'ouverture de « Create » et le
supprime si l'utilisateur annule : qui crée doit pouvoir supprimer.

## Décision

1. Tout membre de l'organisation peut créer un projet (`projects.create`).
2. Le propriétaire d'un projet est son créateur (`Project.created_by`, champ
   amont). Il reçoit le rôle `manager` à la création, par un signal `post_save`
   de `project_rbac` : toutes les voies de création (API, import, duplication)
   sont couvertes sans toucher au code amont.
3. Le rôle du propriétaire ne peut être ni modifié ni révoqué par l'API des
   rôles, y compris par un autre manager.
4. La suppression d'un projet (`projects.delete`) est réservée à son
   propriétaire et à l'administrateur. Les autres managers gèrent tout le reste.
5. L'invitation se fait par adresse e-mail d'un compte existant
   (`POST /api/projects/<pk>/roles/` avec `email` ou `user`). Une adresse
   inconnue est refusée : les comptes sont créés par l'administrateur (ADR 0003).
6. L'administrateur (superutilisateur ou propriétaire de l'organisation) garde
   l'accès à tous les projets.

## Conséquences

- Un projet existant a pour propriétaire son `created_by` ; une migration de
  données lui attribue le rôle `manager` s'il ne l'a pas.
- Pas de transfert de propriété dans l'interface : l'administrateur modifie
  `created_by` dans l'admin Django si quelqu'un quitte le labo.
- Un manager invité peut inviter d'autres personnes et changer les réglages,
  mais pas supprimer le projet ni écarter le propriétaire.
- Un manager apprend si une adresse e-mail correspond à un compte : accepté.
