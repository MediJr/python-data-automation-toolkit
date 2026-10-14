# 0004 — Séquence ordonnée d'étapes, jeux de données nommés, registre d'étapes

**Statut :** Acceptée (finalisation de la phase 0)

## Contexte

La v1.0 mentionnait à la fois une « séquence ordonnée d'étapes » (FR-04) et une « gestion des
dépendances entre étapes » (phase 2). AC-12 et NFR-01 exigent qu'un nouveau type d'étape
puisse être ajouté sans modifier le moteur.

## Décision

- Un workflow est une **liste ordonnée** d'étapes, exécutées dans l'ordre déclaré.
- Les étapes échangent des **jeux de données nommés** : chaque étape déclare ses entrées
  (sources ou sorties d'étapes précédentes) et sa sortie. La validation vérifie qu'une entrée
  est toujours produite avant d'être utilisée.
- **Contrat d'étape** : un modèle de paramètres (Pydantic), une fonction d'exécution qui
  reçoit les jeux de données d'entrée et renvoie le jeu de sortie et un résultat d'étape
  (volumes, avertissements, durée).
- **Registre** : association nom de type → implémentation. Ajouter un type = écrire son
  contrat et l'enregistrer ; un test en fera la démonstration (AC-12).
- Politique d'erreur `stop` (défaut) ou `continue` : avec `continue`, une étape dont une
  entrée nommée n'a pas été produite (parce que l'étape qui la produit a échoué ou a été
  ignorée) est ignorée à son tour, et le statut global devient « partiel ». Ce contrôle suit
  simplement la liste ordonnée et les noms des jeux de données ; il ne nécessite aucun graphe
  de dépendances ni réordonnancement des étapes.
- Aucune reprise automatique : une étape en échec n'est jamais relancée par le moteur
  (ADR-0003).

## Conséquences

- Moteur simple, ordre d'exécution lisible dans la configuration.
- Pas d'exécution parallèle dans le MVP (reportée, §2.2).
- Pas de chargement dynamique de plugins tiers : les types d'étapes sont dans le paquet.

## Alternatives écartées

- **Graphe de dépendances général (tri topologique) :** plus souple, mais inutile pour les
  cas d'utilisation du MVP et plus difficile à rendre lisible.
- **Plugins chargés dynamiquement :** reportés ; ils posent aussi un problème de sécurité
  (exécution de code non maîtrisé).
