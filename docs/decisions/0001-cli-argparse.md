# 0001 — Interface en ligne de commande avec `argparse`

**Statut :** Acceptée (revue de phase 0)

## Contexte

La v1.0 proposait Typer. Le MVP a besoin de quelques sous-commandes (valider, exécuter,
lister les types d'étapes), d'options simples (`--param`, `--overwrite`) et de codes de
sortie documentés. NFR-05 demande d'éviter les dépendances non nécessaires.

## Décision

Utiliser `argparse` de la bibliothèque standard. La commande installée s'appelle
**`data-automate`** (paquet Python `data_automation`) et reste aussi utilisable par
`python -m data_automation`.

## Conséquences

- Aucune dépendance supplémentaire (Typer ajouterait Typer et Click).
- Même approche que le service 1 : aide avec exemples, codes de sortie, tests de la CLI.
- L'aide doit être écrite avec soin (pas de génération automatique à partir des annotations).

## Alternatives écartées

- **Typer :** plus concis, mais deux dépendances pour un gain limité au MVP.
- **Click :** même remarque.
