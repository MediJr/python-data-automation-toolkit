# 0003 — Exécutions complètes et atomiques, pas de mode ajout, reprise reportée

**Statut :** Acceptée (revue de phase 0)

## Contexte

AC-09 exige qu'une répétition ne produise ni doublon ni écrasement involontaire. La v1.0
demandait aussi de distinguer « nouvelle exécution » et « reprise après échec », tout en
précisant (§10) que la reprise complète n'était pas promise au MVP.

## Décision

- Chaque exécution reçoit un identifiant unique **UUID v4**, reporté dans le rapport
  d'exécution et dans les métadonnées de chaque export.
- Chaque exécution part des sources et produit **toutes** ses sorties.
- Chaque sortie est écrite dans un fichier temporaire, relue et vérifiée, puis déplacée à
  son emplacement final ; une sortie existante n'est remplacée qu'avec `--overwrite`.
- Toutes les sorties prévues sont contrôlées **avant** le traitement : si l'une est bloquée,
  rien n'est écrit (méthode éprouvée dans le service 1).
- Aucune sortie n'est écrite en mode ajout dans le MVP.
- La reprise d'un workflow à partir d'une étape et les sorties incrémentales sont reportées.

## Conséquences

- AC-09 est garanti par construction : une répétition réécrit des sorties complètes ou ne
  fait rien.
- Une exécution répétée relit toutes les sources (coût acceptable pour les volumes visés).
- En cas d'échec, les sorties précédentes restent intactes (UC-04).
- Si plusieurs sorties sont produites, un échec après la première peut laisser un ensemble
  mixte (nouvelles et anciennes sorties) ; le rapport le signalera explicitement. Un
  remplacement « tout ou rien » de plusieurs fichiers est une extension possible.

## Alternatives écartées

- **Un dossier par exécution :** rien n'est jamais écrasé, mais l'emplacement change à chaque
  fois, ce qui complique l'import régulier dans Power BI.
- **Reprise dans le MVP :** nécessite de persister l'état et de garantir l'idempotence de
  chaque étape ; trop risqué pour un premier livrable.
