# 0005 — Filtres et calculs déclaratifs, aucune expression évaluée

**Statut :** Acceptée (finalisation de la phase 0)

## Contexte

Le MVP doit filtrer des lignes « selon des conditions déclarées » (§7.3). La solution la plus
rapide serait d'écrire une expression textuelle dans le YAML et de la passer à
`DataFrame.query()` ou `eval()`. NFR-05 interdit l'exécution de code provenant d'une
configuration ; une expression évaluée ouvre cette porte et rend les erreurs moins claires.

## Décision

- Une condition est une structure : `{column, op, value}`, avec `op` choisi dans une liste
  fermée (`eq`, `ne`, `lt`, `le`, `gt`, `ge`, `in`, `not_in`, `is_null`, `not_null`,
  éventuellement `between`, `contains`).
- Plusieurs conditions dans une liste sont combinées par « et » ; une combinaison « ou »
  pourra être ajoutée par une structure explicite (`any_of`).
- Les agrégations utilisent une liste fermée de fonctions (`sum`, `count`, `mean`, `min`,
  `max`).
- Aucune chaîne de la configuration n'est jamais passée à `eval`, `exec`, `query` ou
  équivalent.

## Conséquences

- Pas d'exécution de code via la configuration ; chaque condition est validée (colonne
  existante, opérateur connu, type de valeur compatible).
- Moins expressif qu'un langage d'expressions ; les besoins non couverts se traitent par un
  nouveau type d'étape (ADR-0004).

## Alternatives écartées

- **`DataFrame.query` / `eval` sur du texte :** concis mais contraire à NFR-05.
- **Mini-langage d'expressions avec analyseur dédié :** sûr mais coûteux ; reporté si le
  besoin apparaît.
