# 0004 — Workspaces : dossiers de projets avec membres

Date : 2026-11-20 · Statut : acceptée · Complète les ADR 0001 et 0002

## Contexte

Les rôles se donnent projet par projet (ADR 0001, 0002). Une équipe qui partage
dix projets demande dix invitations par personne, et la liste des projets est
plate. L'édition Enterprise regroupe les projets en workspaces ; l'édition
communautaire n'en affichait qu'un encart désactivé, retiré du fork.

Trois arbitrages validés par Benjamin le 2026-11-20 :

- un workspace porte des droits (ce n'est pas un simple dossier) ;
- un projet appartient à un workspace au plus ;
- tout membre de l'organisation peut créer un workspace.

## Décision

1. Trois modèles dans `project_rbac`, sans migration dans l'app amont
   `projects` (même raison que le point 2 de l'ADR 0001) :
   - `Workspace (organization, title, color, created_by)` ;
   - `WorkspaceProject (workspace, project)`, `project` en `OneToOne` : le lien
     vit ici plutôt que dans un champ de `Project` ;
   - `WorkspaceRole (workspace, user, role)`, avec les trois rôles existants.
2. **Rôle effectif** sur un projet : le plus élevé entre le rôle direct
   (`ProjectRole`) et le rôle hérité du workspace du projet (`WorkspaceRole`),
   dans l'ordre `manager > reviewer > annotator`. `access.get_role` est le seul
   endroit qui le calcule.
3. Les ensembles de rôles de la matrice sont clos vers le haut (si un rôle
   détient une permission, tout rôle supérieur la détient). « Le rôle effectif
   est dans l'ensemble » équivaut donc à « le rôle direct y est, ou le rôle
   hérité y est » : les filtres de listes s'écrivent comme l'union de deux
   sous-requêtes. Un test garde cet invariant.
4. Tout membre crée un workspace. Son créateur en est le propriétaire et reçoit
   le rôle `manager` (signal `post_save`) ; ce rôle n'est ni modifiable ni
   révocable par l'API.
5. Droits sur le workspace lui-même :
   - le voir : ses membres et l'administrateur ;
   - le renommer, gérer ses membres : ses managers et l'administrateur ;
   - le supprimer : son propriétaire et l'administrateur. La suppression
     détache les projets, elle ne les supprime pas.
6. **Rattacher** un projet à un workspace l'ouvre à tous les membres du
   workspace : réservé au propriétaire du projet qui est aussi manager du
   workspace cible, ou à l'administrateur. **Détacher** : le propriétaire du
   projet, un manager du workspace, ou l'administrateur.
7. La suppression d'un projet reste réservée à son propriétaire et à
   l'administrateur (ADR 0002) : un manager hérité ne supprime pas.
8. Les vues des workspaces ne déclarent pas de `permission_required` (elles ne
   visent pas un projet, la matrice ne s'y applique pas) : chacune appelle une
   règle nommée de `access.py`. Un workspace invisible répond 404, une action
   interdite 403.
9. Les listes d'utilisateurs du Data Manager lisent `ProjectMember` (amont).
   Donner un rôle de workspace ou rattacher un projet crée donc les lignes
   `ProjectMember` correspondantes, comme le fait déjà l'API des rôles de projet.
10. `GET /api/projects/?workspace=<id>|none` filtre la liste : un filtre ajouté
    à `ProjectFilterSet` (`projects/api.py`, point d'accroche existant).

## Conséquences

- Un manager de workspace devient manager de tout projet qu'on y range : c'est
  la raison du point 6.
- Qui n'a qu'un rôle direct sur un projet rangé dans un workspace voit le projet
  et le nom du workspace, pas le workspace ni ses autres projets.
- La liste des membres d'un projet montre aussi les membres hérités, en lecture
  seule : on les retire depuis le workspace.
- Retirer un membre d'un workspace, ou détacher un projet, retire aussitôt les
  accès hérités ; les rôles directs restent.
- Pas de workspace personnel implicite : un projet sans workspace reste visible
  de ses seuls membres directs.
