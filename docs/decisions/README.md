# Décisions d'architecture

Chaque fichier décrit une décision : contexte, décision, conséquences et alternatives
écartées. Toutes les décisions ci-dessous sont **acceptées** (0001 à 0008 en phase 0, 0009 pendant les phases 2 à 6).

| N° | Décision | Statut |
| --- | --- | --- |
| [0001](0001-cli-argparse.md) | Interface en ligne de commande avec `argparse` (commande `data-automate`) | Acceptée |
| [0002](0002-configuration-yaml-pydantic.md) | Configuration YAML chargée en mode sûr, validée par Pydantic | Acceptée |
| [0003](0003-executions-atomiques.md) | Exécutions complètes et atomiques, pas de mode ajout, pas de reprise automatique | Acceptée |
| [0004](0004-modele-execution.md) | Séquence ordonnée d'étapes, jeux de données nommés, registre d'étapes | Acceptée |
| [0005](0005-filtres-declaratifs.md) | Filtres et calculs déclaratifs, aucune expression évaluée | Acceptée |
| [0006](0006-securite-des-chemins.md) | Racine de travail et refus des chemins extérieurs | Acceptée |
| [0007](0007-contrat-export-power-bi.md) | Contrat d'export CSV/XLSX pour Power BI et métadonnées | Acceptée |
| [0008](0008-independance-service-1.md) | Aucune dépendance au service 1 dans le MVP | Acceptée |
| [0009](0009-choix-de-realisation.md) | Choix de réalisation des phases 2 à 6 (dossier d'exécution, verrou, codes 4 et 130, paramètres dans les filtres, décimaux exacts, XLSX, modules) | Acceptée |

Ce qui reste à vérifier n'est pas une décision à prendre mais un contrôle à faire pendant le
développement : voir les points ouverts du [cahier des charges](../specification.md#18-décisions-validées-et-points-ouverts).
