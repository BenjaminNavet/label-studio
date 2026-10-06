# 0001 — Droits d'accès par projet dans le fork communautaire

Date : 2026-10-06 · Statut : acceptée

## Contexte

Label Studio Community n'a qu'une organisation et aucun rôle : tout utilisateur
inscrit voit et modifie tous les projets. Les rôles par projet sont réservés à
l'édition Enterprise. Nous voulons héberger plusieurs datasets sur une seule
instance et limiter chaque utilisateur aux projets qui lui sont attribués.

Le code communautaire expose déjà les points d'accroche nécessaires :

- tout contrôle d'accès à un objet (tâche, annotation, prédiction, stockage,
  export, import, backend ML) remonte à `Project.has_permission(user)`, défini
  dans le mixin chargé par le réglage `PROJECT_MIXIN` ;
- chaque vue déclare `permission_required` (une permission par méthode HTTP),
  mais aucune classe de permission ne la lit dans l'édition communautaire ;
- les listes de projets passent en majorité par `Project.objects.for_user(user)`.

## Décision

1. Une app Django séparée, `project_rbac`, porte tout le code : modèle,
   migrations, règles, API, tests. Le code amont n'est modifié qu'aux points
   d'accroche (réglages, `for_user`, quelques `get_queryset`), pour limiter les
   conflits lors des fusions depuis `upstream/develop`.
2. Un modèle `ProjectRole (project, user, role)` propre à l'app, plutôt qu'un
   champ ajouté à `ProjectMember` : pas de migration dans l'app `projects`, donc
   pas de collision de numérotation avec l'amont.
3. Trois rôles par projet :
   - `manager` : tout le projet (réglages, import, export, stockages, ML,
     webhooks, actions du Data Manager, gestion des membres) ;
   - `reviewer` : voir, annoter, modifier ou supprimer toute annotation ;
   - `annotator` : voir, annoter, modifier ou supprimer ses propres annotations.
4. L'administrateur de l'organisation (propriétaire de l'organisation ou
   superutilisateur) voit et gère tous les projets sans rôle explicite. Lui
   seul crée ou supprime des projets.
5. Application :
   - visibilité : `RBACProjectMixin.has_permission` exige un rôle (ou le statut
     d'administrateur), et `for_user` filtre les listes ;
   - actions : `ProjectRolePermission` remplace `HasObjectPermission` dans
     `DEFAULT_PERMISSION_CLASSES`, lit `permission_required` et applique la
     matrice des rôles, au niveau de la vue (projet déduit de l'URL, du
     paramètre `project` ou du corps) et au niveau de l'objet.
   - Une permission absente de la matrice est réservée au `manager` (refus par
     défaut plutôt qu'ouverture par défaut).

## Conséquences

- Les tests amont qui font agir un utilisateur non propriétaire sur un projet
  sans lui donner de rôle échouent désormais : c'est le comportement voulu.
- Les vues qui remplacent `permission_classes` par `IsAuthenticated` échappent à
  la matrice des rôles ; elles restent soumises à la visibilité si elles
  appellent `has_permission`. Elles sont listées et traitées une par une.
- La matrice est un dictionnaire unique (`project_rbac/roles.py`) : changer un
  droit se fait à un seul endroit.
