# CAHIER DES CHARGES — Python Data Automation Toolkit

**Version :** 1.3 — MVP réalisé (phases 1 à 6)
**Statut :** MVP implémenté et testé sous Windows 11 avec Python 3.14.7 ; import dans Power BI Desktop non vérifié (O-2b)
**Type de projet :** outil Python d'automatisation et d'orchestration de traitements de données
**Dépôt prévu :** `python-data-automation-toolkit` (dépôt GitHub indépendant, publié uniquement sur autorisation explicite)
**Positionnement :** service 2 sur 3 du portefeuille d'outils de traitement des données

---

## 0. Historique et changements

| Version | Contenu |
| --- | --- |
| 1.0 | Proposition initiale. |
| 1.1 | Revue de phase 0 : incohérences corrigées et premières décisions (C-01 à C-15). |
| 1.2 | Finalisation de la phase 0 : décisions 0004 à 0008 acceptées, format CSV, nom de commande, identifiant d'exécution, licence, critère pour FR-19, exclusions du MVP explicitées (C-16 à C-22). |
| 1.3 | Réalisation des phases 1 à 6 : choix de réalisation regroupés dans la décision 0009 (C-23) ; statut des phases et du point O-2b mis à jour. Périmètre inchangé. |

Les v1.2 et v1.3 conservent le périmètre, les objectifs et la structure de la v1.0. Chaque décision est
détaillée dans [`decisions/`](decisions/README.md).

| Réf. | Section(s) | Changement | Raison |
| --- | --- | --- | --- |
| C-01 | §4 FR-15, AC-12 | FR-15 (ajout de types d'étapes) passe de **P1 à P0**. | AC-12 et NFR-01 exigeaient cette capacité dans le MVP ; le registre d'étapes est le cœur de l'architecture ([ADR-0004](decisions/0004-modele-execution.md)). |
| C-02 | §4 FR-16, §9.2 | FR-16 est scindée : **FR-16a (P0)** codes de sortie documentés et exemple pour le Planificateur de tâches Windows ; **FR-16b (P1)** autres mécanismes. | Le §9.2 exigeait déjà la compatibilité avec un planificateur externe dans le MVP. |
| C-03 | §9.3, §10, AC-09 | Exécutions **complètes et atomiques** ; aucune sortie en mode ajout dans le MVP ; la reprise après échec est reportée. | Rend AC-09 vérifiable par construction et supprime la contradiction avec le §10 ([ADR-0003](decisions/0003-executions-atomiques.md)). |
| C-04 | §3 UC-01, §4 | Nouvelle exigence **FR-19 (P0)** : paramètres d'exécution (ex. `period`) utilisables dans les chemins et les filtres ; fuseau horaire explicite. | La sélection « par période » de UC-01 n'était couverte par aucune exigence. |
| C-05 | §4 FR-04, §5.2, §15 | Modèle d'exécution : **séquence ordonnée d'étapes échangeant des jeux de données nommés** ; pas de graphe de dépendances général. | La v1.0 hésitait entre séquence et gestion de dépendances ([ADR-0004](decisions/0004-modele-execution.md)). |
| C-06 | §3 UC-03, §9.1 | Rapport métier = fichiers d'indicateurs + synthèse Markdown ; rapport technique = rapport d'exécution JSON (+ résumé Markdown). | Le contenu du « rapport métier » n'était pas défini. |
| C-07 | §7.2, §14 | Les jointures déclarent leur **relation attendue** et contrôlent le nombre de lignes ; nouveau critère AC-16. | Rendre vérifiable la détection d'une « multiplication inattendue des lignes ». |
| C-08 | §8, §14 | **Contrat d'export Power BI** et fichier de métadonnées JSON à côté de chaque export. | Préciser « prêt pour Power BI » sans promettre l'intégration au service cloud ([ADR-0007](decisions/0007-contrat-export-power-bi.md)). |
| C-09 | §7.3, §11 NFR-05 | Les filtres et calculs sont des **structures déclaratives**, jamais des expressions textuelles évaluées. | NFR-05 interdit l'exécution de code provenant de la configuration ; `DataFrame.query`/`eval` sur du texte de configuration y contreviendrait ([ADR-0005](decisions/0005-filtres-declaratifs.md)). |
| C-10 | §11 NFR-05, §14 | **Racine de travail** déclarée ; tout chemin en dehors est refusé ; YAML chargé uniquement en mode sûr ; nouveau critère AC-15. | Rendre vérifiable « limiter les accès aux emplacements autorisés » ([ADR-0006](decisions/0006-securite-des-chemins.md)). |
| C-11 | §5.3 | CLI avec **`argparse`** au lieu de Typer. | Une dépendance de moins (NFR-05) et cohérence avec le service 1 ([ADR-0001](decisions/0001-cli-argparse.md)). |
| C-12 | §5.3, §5.4 | YAML + Pydantic confirmés ; Ruff en dépendance de développement uniquement ; versions figées et vérifiées en phase 1. | [ADR-0002](decisions/0002-configuration-yaml-pydantic.md). |
| C-13 | §7.4 | **Aucune dépendance** au service 1 dans le MVP ; seules ses méthodes sont reprises. | Éviter le couplage entre projets ([ADR-0008](decisions/0008-independance-service-1.md)). |
| C-14 | §12 | Structure de départ plus plate ; les sous-dossiers sont créés seulement quand un module le justifie. | Conforme à la règle de la v1.0 : « pas de modules vides ». |
| C-15 | §15, §18 | Documentation publique en anglais ; documents de cadrage en français. | Cohérence avec le service 1 publié et avec le public visé (recruteurs, clients). |
| C-16 | §18, `decisions/` | Décisions 0004 à 0008 **acceptées**. | Validation de la phase 0. |
| C-17 | §8.2, §8.3, ADR-0007 | CSV en **UTF-8 sans BOM**, dates ISO 8601, séparateur décimal point ; contrat XLSX ajouté ; attentes d'import Power BI et limites non vérifiées documentées. | Validation de la phase 0 ; ferme le point ouvert O-2 (sauf vérification dans Power BI Desktop, O-2b). |
| C-18 | §5.2, §12, ADR-0001 | Commande CLI **`data-automate`**, paquet `data_automation`. | Ferme le point ouvert O-3. |
| C-19 | §9.1, NFR-04, ADR-0003, ADR-0007 | Identifiant d'exécution **UUID v4**. | Ferme le point ouvert O-4. |
| C-20 | §18, `LICENSE` | Licence **MIT**, « Copyright (c) 2026 LUMU BAMANA MANASSE », fichier identique à celui du service 1. | Ferme le point ouvert O-5 ; titulaire vérifié (voir §18). |
| C-21 | §14 | Nouveau critère **AC-18** pour FR-19 ; AC-04 couvre CSV et XLSX. | FR-19 (P0) n'avait pas de critère d'acceptation. |
| C-22 | §2.3, ADR-0004 | Liste explicite des **exclusions du MVP** ; la politique `continue` suit les jeux de données nommés sans graphe de dépendances. | Garantir qu'aucune décision n'impose une fonctionnalité reportée. |
| C-23 | §4 FR-19, §9, §10, §12, ADR-0009 | Choix de réalisation : dossier d'exécution par exécution, verrou, codes de sortie 4 (partiel) et 130 (interrompu), paramètres dans les filtres par `param:`, clé de jointure `keys`, refus des clés YAML non textuelles, décimaux exacts, contrôle des nombres XLSX, defusedxml, découpage en modules. | Trancher les détails rencontrés pendant la réalisation sans changer le périmètre ([ADR-0009](decisions/0009-choix-de-realisation.md)). |

---

## 1. Présentation générale

### 1.1. Contexte

Les entreprises reçoivent régulièrement des données provenant de plusieurs fichiers,
systèmes et services. Les mêmes opérations sont souvent répétées manuellement : récupérer
les fichiers, vérifier leur structure, consolider plusieurs sources, appliquer des
transformations, calculer des indicateurs, préparer des fichiers pour Power BI, produire des
rapports périodiques et vérifier que le traitement s'est terminé correctement.

Ces opérations mobilisent du temps et augmentent le risque d'erreur humaine. Le projet vise à
fournir un outil Python configurable qui transforme ces opérations en workflows automatisés,
reproductibles, contrôlables et extensibles.

### 1.2. Vision

Un toolkit modulaire permettant de définir un workflow de traitement de données, de
l'exécuter manuellement ou par une planification externe, et d'obtenir des résultats
vérifiés et documentés. De nouveaux connecteurs, transformations et déclencheurs doivent
pouvoir être ajoutés sans modifier le moteur central.

### 1.3. Objectifs principaux

1. Automatiser les tâches répétitives de traitement de données.
2. Consolider plusieurs fichiers et sources compatibles.
3. Produire des jeux de données prêts à être importés dans Power BI.
4. Générer des rapports périodiques et des indicateurs.
5. Garantir la traçabilité des exécutions et des erreurs.
6. Permettre l'ajout de nouveaux traitements par modules.
7. Fournir une base suffisamment fiable pour un usage professionnel, sans prétendre à une
   certification de production non démontrée.

---

## 2. Périmètre fonctionnel

Le projet est centré sur l'automatisation de workflows de données, et non sur une collection
de scripts indépendants.

### 2.1. MVP

- découverte et lecture de fichiers CSV et Excel ;
- traitement de plusieurs fichiers au cours d'une même exécution ;
- paramètres d'exécution (ex. période) utilisables dans les chemins et filtres *(C-04)* ;
- consolidation de données provenant de plusieurs fichiers ;
- enchaînement ordonné d'étapes configurables échangeant des jeux de données nommés *(C-05)* ;
- transformations courantes (filtres déclaratifs, projections, renommages, conversions de
  type, jointures, agrégations) ;
- validation des prérequis et des résultats ;
- export de fichiers prêts pour Power BI, avec métadonnées *(C-08)* ;
- rapports d'exécution (techniques) et synthèses d'indicateurs (métier) *(C-06)* ;
- journalisation des opérations ;
- gestion des erreurs, protection des sorties existantes, écriture atomique *(C-03)* ;
- interface en ligne de commande ;
- configuration déclarative validée avant exécution ;
- exécutions répétées sûres (aucun doublon ni écrasement non autorisé) ;
- ajout de nouveaux types d'étapes via un registre *(C-01)* ;
- exemple documenté de planification par le Planificateur de tâches Windows *(C-02)*.

### 2.2. Versions ultérieures

Connecteurs bases de données et API ; nouveaux types de transformations ; notifications par
e-mail ; planificateur intégré ; exécution parallèle ; interface graphique ou web ; gestion
centralisée de plusieurs workflows ; intégration Microsoft plus poussée ; système de plugins
tiers documenté ; **reprise d'un workflow après échec** *(C-03)* ; **sorties en mode ajout**
(historisation incrémentale) avec garanties d'idempotence *(C-03)*.

Ces éléments ne doivent pas retarder la livraison du noyau fonctionnel.

### 2.3. Exclusions explicites du MVP *(C-22)*

Aucune exigence, décision ni critère d'acceptation du MVP ne doit imposer :

| Exclu du MVP | Ce que le MVP fait à la place | Référence |
| --- | --- | --- |
| Reprise automatique après échec | Une étape en échec n'est jamais relancée ; une nouvelle exécution complète est lancée par l'utilisateur ou le planificateur. | ADR-0003, ADR-0004, §9.3 |
| Planificateur interne | Codes de sortie et exemple pour le Planificateur de tâches Windows (planification externe). | FR-16a, §9.2 |
| Graphe général de dépendances | Liste ordonnée d'étapes et jeux de données nommés. | FR-04, ADR-0004 |
| Dépendance obligatoire au service 1 | Paquet autonome ; une intégration optionnelle pourra venir plus tard. | §7.4, ADR-0008 |
| Intégration directe à Power BI Service | Fichiers d'export conformes à un contrat, avec métadonnées. | §8, ADR-0007 |

---

## 3. Cas d'utilisation prioritaires

### UC-01 — Consolidation mensuelle des ventes

Chaque mois, plusieurs fichiers de ventes d'agences différentes. Le toolkit doit :

1. sélectionner les fichiers de la période passée en paramètre (ex. `--param period=2026-09`)
   d'après un motif de chemin configuré *(C-04)* ;
2. vérifier qu'ils possèdent les colonnes requises ;
3. harmoniser les types nécessaires ;
4. réunir les enregistrements dans un jeu consolidé, en conservant la provenance de chaque
   ligne (fichier source) ;
5. contrôler les volumes et les résultats ;
6. exporter un fichier destiné à Power BI ;
7. produire un rapport indiquant les fichiers traités, les volumes et les anomalies.

### UC-02 — Préparation récurrente des données pour Power BI

Lire les sources configurées, appliquer les transformations déclarées, produire une table au
format défini, vérifier colonnes, types et contraintes, exporter dans un emplacement connu et
conserver les métadonnées d'audit.

### UC-03 — Rapport périodique automatique

Charger les données de la période, calculer les indicateurs configurés, produire les fichiers
de résultats et une **synthèse Markdown des indicateurs** (rapport métier), générer le
**rapport d'exécution** (rapport technique), identifier erreurs et données manquantes, et
permettre une nouvelle exécution sans doublon ni écrasement non autorisé *(C-03, C-06)*.

### UC-04 — Échec d'une étape

Un fichier attendu est absent ou mal structuré. Le toolkit doit détecter le problème,
identifier l'étape concernée, consigner l'erreur, appliquer la politique d'erreur configurée,
ne jamais présenter un résultat incomplet comme valide et **laisser intactes les sorties
précédentes** tant qu'une nouvelle sortie n'a pas été validée.

---

## 4. Exigences fonctionnelles

| ID | Exigence | Priorité |
| --- | --- | --- |
| FR-01 | Charger plusieurs fichiers CSV et Excel selon une configuration | P0 |
| FR-02 | Sélectionner les fichiers selon un motif et un répertoire configurés | P0 |
| FR-03 | Consolider des fichiers par ajout de lignes ou rapprochement de tables | P0 |
| FR-04 | Exécuter une séquence ordonnée d'étapes échangeant des jeux de données nommés | P0 |
| FR-05 | Appliquer des filtres déclaratifs, projections, renommages et transformations simples | P0 |
| FR-06 | Calculer des agrégations et indicateurs courants | P0 |
| FR-07 | Vérifier les préconditions, colonnes et types attendus | P0 |
| FR-08 | Exporter des jeux de données structurés pour Power BI, avec métadonnées | P0 |
| FR-09 | Générer un rapport d'exécution JSON et une synthèse lisible | P0 |
| FR-10 | Enregistrer les durées, volumes, étapes et erreurs | P0 |
| FR-11 | Empêcher les écrasements accidentels ; écriture atomique des sorties | P0 |
| FR-12 | Retourner un code de sortie exploitable par un script externe | P0 |
| FR-13 | Exécuter un workflow depuis la ligne de commande | P0 |
| FR-14 | Permettre une configuration déclarative validée avant exécution | P0 |
| FR-15 | Permettre l'ajout de nouveaux types d'étapes via un registre | **P0** *(C-01)* |
| FR-16a | Codes de sortie documentés et exemple pour le Planificateur de tâches Windows | **P0** *(C-02)* |
| FR-16b | Exemples pour d'autres planificateurs (cron, etc.) après validation de la plateforme | P1 *(C-02)* |
| FR-17 | Notifications configurables | P2 |
| FR-18 | Interface graphique | P2 |
| FR-19 | Paramètres d'exécution utilisables dans les chemins et filtres, fuseau horaire explicite | **P0** *(C-04)* |

P0 : indispensable au MVP. P1 : version suivante. P2 : extension non prioritaire.

---

## 5. Architecture technique

### 5.1. Principes

Séparation entre moteur, étapes, entrées-sorties et rapports ; configuration indépendante du
code ; interfaces explicites ; dépendances limitées au nécessaire ; tests unitaires et
d'intégration ; ajout de traitements sans réécrire le moteur ; erreurs explicites et
exécutions observables.

### 5.2. Composants

1. **Interface CLI** (`data-automate`, aussi `python -m data_automation`) : commandes,
   arguments, validation des chemins, lancement des workflows.
2. **Moteur d'orchestration** : lit le workflow validé, exécute les étapes dans l'ordre,
   transmet les jeux de données nommés, applique la politique d'erreur et calcule le statut.
3. **Registre des étapes** : associe un nom de type d'étape à une implémentation respectant
   un contrat commun (paramètres validés, entrées nommées, sorties nommées, résultat
   d'étape). Ajouter un type d'étape = l'implémenter et l'enregistrer *(C-01)*.
4. **Connecteurs d'entrée et de sortie** : lecture et écriture des fichiers ; écriture
   atomique et vérification par relecture. Les futurs connecteurs SQL ou API s'ajouteront
   sans réécrire les transformations.
5. **Transformations** : consolidation, filtres, jointures, agrégations, préparation.
6. **Journalisation et reporting** : journaux, statistiques, rapport technique, synthèse
   métier, diagnostics.

Le modèle d'exécution est décrit dans [ADR-0004](decisions/0004-modele-execution.md).

### 5.3. Technologies

| Composant | Choix | Justification |
| --- | --- | --- |
| Langage | Python | Cohérence avec les trois services |
| Données | pandas | Consolidation, jointures, agrégations |
| CSV / Excel | `csv`, pandas, openpyxl | Formats courants |
| CLI | **`argparse`** *(C-11)* | Bibliothèque standard ; une dépendance de moins ; cohérent avec le service 1 |
| Configuration | **YAML (PyYAML, `safe_load`) + Pydantic** | Workflows lisibles ; validation stricte avec erreurs précises |
| Journalisation | `logging` | Niveaux de gravité, sans dépendance |
| Tests | pytest | Unitaires et intégration |
| Qualité | Ruff (**développement uniquement**) | Linting |
| Packaging | `pyproject.toml` | Installation et distribution |

Versions disponibles sur PyPI au moment de la revue : pydantic 2.14.1 (pydantic-core 2.50.1),
PyYAML 6.0.3. Les versions exactes seront fixées et **vérifiées par une installation réelle**
en phase 1 (voir §18, point ouvert O-1).

### 5.4. Compatibilité

Cible initiale : Windows 11 et Python 3.14 (environnement de développement). Pas de
dépendance inutile au système. La compatibilité avec d'autres systèmes ou versions de Python
ne sera annoncée qu'après exécution des tests sur ces environnements.

---

## 6. Modèle de workflow

Un workflow contient : un identifiant stable, une version de schéma de configuration, une
description, la racine de travail *(C-10)*, les paramètres d'exécution attendus *(C-04)*, les
sources d'entrée, la liste ordonnée des étapes, les sorties, la politique d'erreur, les
paramètres de validation et les options de rapport.

### 6.1. Exemple conceptuel

Illustratif : il décrit le comportement attendu, pas une implémentation disponible. Le schéma
définitif sera fixé en phase 1.

```yaml
workflow:
  id: monthly-sales-report
  schema_version: 1
  description: Consolidation mensuelle des ventes des agences
  root: .                      # tous les chemins sont relatifs à cette racine (C-10)

parameters:
  period: {type: month, required: true}   # ex. --param period=2026-09 (C-04)

inputs:
  - id: sales_files
    type: csv
    path: "data/incoming/{period}/sales_*.csv"
    required_columns: [region, order_id, amount]
    on_empty_match: fail       # aucun fichier trouvé = échec explicite

steps:
  - id: consolidate_sales
    type: concatenate
    input: sales_files
    output: sales
    add_source_column: source_file

  - id: only_closed_orders
    type: filter
    input: sales
    output: closed_sales
    where:                     # condition déclarative, jamais une expression évaluée (C-09)
      - {column: status, op: eq, value: closed}

  - id: calculate_kpis
    type: aggregate
    input: closed_sales
    output: kpis
    group_by: [region]
    metrics:
      total_sales: {column: amount, function: sum}
      order_count: {column: order_id, function: count}

outputs:
  - id: export_powerbi
    input: kpis
    type: csv
    path: "data/output/monthly_sales_{period}.csv"
    expected_columns: [region, total_sales, order_count]

on_error: stop                 # stop | continue (voir §10)
report:
  formats: [json, markdown]
```

### 6.2. Validation préalable

Avant toute exécution : validité du schéma (Pydantic), clés inconnues refusées, paramètres
obligatoires fournis, chemins dans la racine de travail, sources requises présentes, types
d'étapes enregistrés, **chaque entrée d'étape produite par une étape précédente ou une
source**, sorties qui ne collisionnent pas. En cas d'erreur : messages précis, aucun
traitement démarré, code de sortie dédié.

---

## 7. Consolidation et transformations

### 7.1. Consolidation verticale

Réunir des fichiers de schéma compatible, en gérant explicitement les colonnes obligatoires,
les colonnes supplémentaires, l'ordre des colonnes, les incompatibilités, les fichiers vides
et illisibles. Chaque anomalie suit une politique configurable et documentée (échec,
avertissement, exclusion du fichier avec mention au rapport). La provenance des lignes peut
être conservée dans une colonne.

### 7.2. Jointures *(C-07)*

Paramètres : sources, colonnes de clé, type de jointure, **relation attendue**
(`one_to_one`, `many_to_one`, `one_to_many`), règles pour les clés manquantes. Le moteur
compare le nombre de lignes avant et après la jointure et échoue si la relation déclarée est
violée (multiplication inattendue des lignes).

### 7.3. Agrégations et indicateurs

Somme, comptage, moyenne, minimum, maximum, regroupement par dimensions, filtrage par
**conditions déclaratives** (colonne, opérateur choisi dans une liste fermée, valeur) *(C-09)*.
Calculs déterministes : mêmes données et configuration, mêmes résultats (hors métadonnées
variables comme l'heure d'exécution).

### 7.4. Relation avec le service 1 *(C-13)*

`python-data-cleaning-toolkit` reste spécialisé dans le nettoyage et la normalisation. Le MVP
du service 2 **n'en dépend pas** et ne réimplémente pas ses règles de nettoyage ; il en
reprend les méthodes éprouvées (écriture atomique, relecture de vérification, statuts
distincts, protection des sources). Une étape d'intégration optionnelle pourra être ajoutée
plus tard si elle est utile, stable et testée.

---

## 8. Préparation pour Power BI

### 8.1. Objectif

Produire des jeux de données structurés, cohérents et documentés que Power BI peut importer.
Le MVP couvre la préparation et l'export, pas les tableaux de bord ni le rafraîchissement
dans Power BI Service.

### 8.2. Formats

CSV en **UTF-8 sans BOM** (format recommandé) ; XLSX lorsque le besoin le justifie. Parquet
pourra être étudié plus tard.

### 8.3. Contrat d'export *(C-08, C-17)*

Détaillé dans [ADR-0007](decisions/0007-contrat-export-power-bi.md) :

- CSV : UTF-8 sans BOM, délimiteur `,`, dates ISO 8601, séparateur décimal `.`, sans
  séparateur de milliers, en-tête unique, noms de colonnes stables, valeurs manquantes en
  cellules vides ;
- XLSX : nombres en cellules numériques, dates en cellules de date au format `yyyy-mm-dd`,
  identifiants en texte, aucune formule créée à partir d'un texte.

Avant de déclarer un export réussi : colonnes attendues présentes et nommées, types logiques
conformes, aucune colonne obligatoire manquante, nombre de lignes cohérent, fichier relu et
vérifié. Chaque export est accompagné d'un fichier `<nom>.metadata.json` (identifiant du
workflow, identifiant d'exécution UUID v4, date, paramètres, sources et leurs empreintes,
contrôles effectués, schéma des colonnes, format du fichier).

**Attentes d'import dans Power BI Desktop (non vérifiées dans le logiciel) :** l'encodage
peut devoir être fixé à « 65001 : Unicode (UTF-8) » faute de BOM, et les types numériques
peuvent devoir être convertis avec les paramètres régionaux `en-US` lorsque Power BI est
configuré en français. Ces points sont détaillés dans l'ADR-0007 et resteront présentés comme
non testés tant qu'un import réel n'aura pas été fait (point ouvert O-2b).

### 8.4. Modèle analytique

Le toolkit peut préparer des tables de faits et de dimensions sans imposer un modèle unique.
La publication d'un fichier ne signifie pas que le rafraîchissement d'un rapport Power BI
Service est pris en charge.

---

## 9. Rapports récurrents et planification

### 9.1. Rapports *(C-06)*

- **Rapport technique** (JSON + résumé Markdown) pour chaque exécution : workflow, identifiant
  d'exécution (UUID v4), heures de début et de fin (UTC), paramètres, statut global, étapes exécutées
  avec leur statut et leur durée, volumes lus et produits, fichiers générés, avertissements,
  erreurs rattachées à leur étape.
- **Rapport métier** : les fichiers d'indicateurs produits et, si configuré, une synthèse
  Markdown de ces indicateurs.

### 9.2. Planification externe *(C-02)*

Le MVP fournit une commande exécutable, des codes de sortie documentés et un exemple pour le
Planificateur de tâches Windows. Cron et les autres planificateurs seront documentés après
validation de leur plateforme. Pas de planificateur interne dans le MVP.

### 9.3. Exécutions répétées *(C-03)*

Chaque exécution est complète et produit ses sorties de façon atomique. Une sortie existante
n'est remplacée qu'avec une autorisation explicite (`--overwrite`) et seulement après
validation de la nouvelle. Aucune sortie n'est écrite en mode ajout dans le MVP : une
répétition ne peut donc pas dupliquer des données. La reprise d'un workflow après échec et
les sorties incrémentales sont reportées (§2.2).

---

## 10. Fiabilité et gestion des erreurs

1. Toute erreur est identifiable et rattachée à une étape.
2. Un workflow incomplet n'est jamais déclaré réussi.
3. Les sorties finales ne sont publiées (déplacées à leur emplacement) qu'après validation.
4. Les sorties existantes sont protégées par défaut.
5. Les erreurs sont journalisées sans exposer de données sensibles.
6. Une étape dont une entrée est absente ou invalide n'est pas exécutée.
7. Politique d'erreur explicite : `stop` (par défaut) arrête le workflow ; `continue` poursuit
   uniquement les étapes qui ne dépendent pas d'une étape en échec, et le statut global est
   alors « partiel », jamais « réussi ».

Écriture sécurisée : fichier temporaire, relecture, remplacement contrôlé
([ADR-0003](decisions/0003-executions-atomiques.md)).

---

## 11. Exigences non fonctionnelles

- **NFR-01 Extensibilité :** ajouter un type d'étape = implémenter son contrat et l'enregistrer,
  sans modifier le moteur.
- **NFR-02 Maintenabilité :** responsabilités distinctes, noms explicites, annotations de
  types, documentation suffisante.
- **NFR-03 Reproductibilité :** mêmes configuration, paramètres et sources = résultats
  équivalents ; les paramètres influents sont enregistrés dans le rapport.
- **NFR-04 Traçabilité :** identifiant unique par exécution (UUID v4) et rapport exploitable.
- **NFR-05 Sécurité *(C-09, C-10)* :** racine de travail déclarée et chemins hors racine
  refusés ; YAML en mode sûr ; aucune expression ni code évalué depuis la configuration ;
  aucun secret dans les rapports ; sources jamais modifiées (empreinte vérifiée avant et
  après) ; sorties gérées explicitement ; dépendances minimales.
- **NFR-06 Performance :** pas de lectures ni copies inutiles. Benchmarks reproductibles ; les
  seuils seront fixés après une première mesure de référence. Le service 1 a mesuré la
  lecture XLSX environ 4 fois plus lente que le CSV : les exemples privilégieront le CSV.
- **NFR-07 Observabilité :** journaux indiquant quoi, dans quel ordre, avec quels résultats et
  quand.
- **NFR-08 Compatibilité :** versions de Python et systèmes pris en charge déclarés et
  vérifiés par des tests.

---

## 12. Structure de dépôt envisagée *(C-14)*

Point de départ volontairement plat ; un module devient un sous-paquet seulement quand sa
taille le justifie.

```text
python-data-automation-toolkit/
├── README.md, pyproject.toml, .gitignore, .gitattributes
├── LICENSE             # MIT, déjà présent (identique au service 1)
├── src/data_automation/
│   ├── cli.py          # argparse, commande data-automate, codes de sortie
│   ├── config.py       # modèles Pydantic, chargement YAML sûr, paramètres
│   ├── engine.py       # exécution ordonnée, politique d'erreur, statuts
│   ├── registry.py     # contrat d'étape et registre
│   ├── steps/          # implémentations des types d'étapes
│   ├── io.py           # lecture multi-fichiers, écriture atomique, vérification
│   ├── paths.py        # racine de travail, motifs, paramètres
│   └── reporting.py    # rapport technique, synthèse métier, métadonnées d'export
├── config/examples/    # workflows d'exemple
├── data/sample/        # données synthétiques
├── reports/examples/   # sorties réelles d'exemple
├── tests/              # unit/, integration/, cli/ selon les besoins
├── benchmarks/
└── docs/               # architecture, configuration, workflows, powerbi, testing,
                        # limitations, decisions/
```

---

## 13. Stratégie de tests

- **Unitaires :** configuration (y compris clés inconnues et paramètres manquants), chaque
  type d'étape, consolidation, jointures (y compris violation de relation), agrégations,
  filtres, rapports, contrôle des chemins et des écrasements, gestion d'erreur.
- **Intégration :** workflows complets lisant plusieurs fichiers, produisant les sorties
  attendues (comparées à des résultats écrits à la main), générant un rapport cohérent, et
  échouant explicitement sur une source invalide.
- **Non-régression :** chaque défaut corrigé, fichiers vides, schémas incompatibles, chemins
  invalides, résultats incomplets.
- **CLI :** commandes, options, messages, codes de sortie, configuration invalide, exécution
  depuis un autre répertoire de travail.
- **Reproductibilité :** deux exécutions identiques donnent des résultats équivalents, hors
  métadonnées variables.
- **Sécurité :** chemins hors racine, tentative d'écrasement, YAML malveillant (balises
  Python) refusé.
- **Vérification indépendante et mutations :** comme pour le service 1, un vérificateur qui
  n'importe pas le paquet, et la désactivation volontaire de chaque protection pour s'assurer
  qu'un test échoue.

---

## 14. Critères d'acceptation du MVP

| ID | Critère |
| --- | --- |
| AC-01 | Une configuration valide est chargée et validée avant exécution ; une configuration invalide est refusée avec un message précis. |
| AC-02 | Plusieurs fichiers CSV sont consolidés dans un workflow unique. |
| AC-03 | Au moins un filtre, une jointure et une agrégation configurés sont appliqués. |
| AC-04 | Un export CSV et un export XLSX destinés à Power BI sont générés selon le contrat de l'ADR-0007, vérifiés par relecture et accompagnés de leurs métadonnées. |
| AC-05 | Le rapport d'exécution contient statut, étapes, volumes, durées et erreurs. |
| AC-06 | Une source manquante ou invalide provoque un échec explicite, rattaché à son étape. |
| AC-07 | Les fichiers sources sont préservés (empreinte identique avant et après). |
| AC-08 | Les sorties existantes ne sont pas écrasées sans autorisation explicite. |
| AC-09 | Le même workflow exécuté plusieurs fois ne produit ni doublon ni écrasement involontaire (sorties atomiques, pas de mode ajout). |
| AC-10 | La CLI est documentée et testée. |
| AC-11 | Les tests unitaires et d'intégration passent dans l'environnement officiellement pris en charge. |
| AC-12 | Un nouveau type d'étape peut être ajouté via le registre sans modifier le moteur (démontré par un test). |
| AC-13 | Un exemple complet de workflow est reproductible depuis une installation propre. |
| AC-14 | Le dépôt contient les instructions d'installation, d'utilisation, de configuration et de dépannage. |
| AC-15 | Un chemin hors de la racine de travail et un YAML contenant une balise d'exécution sont refusés *(C-10)*. |
| AC-16 | Une jointure qui viole la relation déclarée échoue explicitement *(C-07)*. |
| AC-17 | Un exemple de planification par le Planificateur de tâches Windows est documenté et sa commande testée *(C-02)*. |
| AC-18 | Un paramètre d'exécution (ex. `period`) sélectionne les fichiers de la période demandée ; un paramètre obligatoire absent ou mal formé est refusé avant exécution *(FR-19, C-21)*. |

---

## 15. Plan de réalisation

| Phase | Contenu | Livrable |
| --- | --- | --- |
| 0 — Cadrage | Périmètre, cas d'utilisation, modèle d'exécution, format de configuration, décisions, licence | **Ce document v1.2, les 8 décisions acceptées et `LICENSE`** (terminé) |
| 1 — Socle | Structure, packaging, versions figées et installées, CLI minimale, modèles de configuration, racine de travail, journalisation, tests de base | Outil installable qui valide un workflow |
| 2 — Moteur | Registre et contrat d'étape, exécution ordonnée, jeux de données nommés, statuts, politique d'erreur | Moteur avec étapes simples |
| 3 — Transformations | Lecture multi-fichiers, paramètres, concaténation, filtres, jointures, agrégations, contrôles de schéma | Premier workflow métier complet |
| 4 — Exports et rapports | Export CSV/XLSX vérifié, métadonnées, rapport technique, synthèse métier, exemples Power BI | Workflow de consolidation et d'export reproductible |
| 5 — Fiabilité | Protection des sorties, tests de répétition, codes de sortie, exemple Planificateur de tâches | Workflow utilisable de façon récurrente |
| 6 — Publication | Tests finaux, benchmark, audit de sécurité, documentation (anglais), revue des fichiers, publication après autorisation | Dépôt autonome et publiable |

Chaque phase se termine par un rapport (fichiers, tests exécutés et résultats, problèmes
ouverts) avant de passer à la suivante.

**État (v1.3) :** phases 0 à 6 réalisées. Les tests, le benchmark et les limites sont
décrits en anglais dans `docs/testing.md`, `docs/performance.md` et `docs/limitations.md`.

---

## 16. Hors périmètre

Le MVP ne doit pas devenir : un orchestrateur distribué de type Airflow, un entrepôt de
données, un moteur de base de données, un outil de visualisation remplaçant Power BI, une
plateforme SaaS, un service de nettoyage dupliquant le service 1, ni un moteur de requêtes
SQL (service 3, projet distinct).

---

## 17. Risques et mesures

| Risque | Conséquence | Mesure |
| --- | --- | --- |
| Périmètre trop large | Projet difficile à terminer | MVP limité à UC-01 à UC-04 ; reprise et mode ajout reportés |
| Architecture trop complexe | Maintenance difficile | Séquence ordonnée, contrat d'étape simple, pas de graphe général ni de plugins |
| Répétitions mal gérées | Doublons ou écrasements | Sorties atomiques, protection par défaut, tests de répétition |
| Sources incompatibles | Résultats erronés | Validation des schémas avant consolidation |
| Jointure qui multiplie les lignes | Indicateurs faux | Relation déclarée et contrôle des volumes (AC-16) |
| Résultats partiels présentés comme valides | Mauvaises décisions | Statuts distincts (réussi, partiel, échec) et validation des exports |
| Exécution de code via la configuration | Faille de sécurité | YAML sûr, filtres déclaratifs, aucune évaluation d'expression |
| Couplage au service 1 | Dépendance entre projets | Aucune dépendance dans le MVP |
| Promesse excessive sur Power BI | Attentes déçues | Contrat d'export précis, sans intégration au service cloud |
| Bibliothèque binaire bloquée par la politique de sécurité Windows (déjà observé avec numpy) | Installation impossible | Vérification par installation réelle en phase 1 ; procédure de contournement documentée |

---

## 18. Décisions validées et points ouverts

### Décisions (phase 0 finalisée)

| # | Décision | Statut |
| --- | --- | --- |
| 1 | MVP : sources CSV et Excel, consolidation, transformations, rapports, exports CSV et XLSX | Validée |
| 2 | Configuration YAML (mode sûr) + Pydantic | Validée ([ADR-0002](decisions/0002-configuration-yaml-pydantic.md)) |
| 3 | Planification externe dans le MVP, sans planificateur interne | Validée, avec FR-16a en P0 |
| 4 | Power BI : préparation de fichiers selon un contrat, sans intégration à Power BI Service | Validée ([ADR-0007](decisions/0007-contrat-export-power-bi.md)) |
| 5 | Séquence ordonnée d'étapes, jeux de données nommés, registre d'étapes, sans plugins ni graphe général | Validée ([ADR-0004](decisions/0004-modele-execution.md)) |
| 6 | Dépôt GitHub indépendant, aucune publication sans autorisation explicite | Validée |
| 7 | CLI avec `argparse`, commande `data-automate` | Validée ([ADR-0001](decisions/0001-cli-argparse.md)) |
| 8 | Exécutions atomiques, pas de mode ajout, pas de reprise automatique | Validée ([ADR-0003](decisions/0003-executions-atomiques.md)) |
| 9 | Filtres et calculs déclaratifs, aucune expression évaluée | Validée ([ADR-0005](decisions/0005-filtres-declaratifs.md)) |
| 10 | Racine de travail et refus des chemins extérieurs | Validée ([ADR-0006](decisions/0006-securite-des-chemins.md)) |
| 11 | Aucune dépendance au service 1 dans le MVP | Validée ([ADR-0008](decisions/0008-independance-service-1.md)) |
| 12 | CSV en UTF-8 sans BOM, dates ISO 8601, séparateur décimal point | Validée ([ADR-0007](decisions/0007-contrat-export-power-bi.md)) |
| 13 | Identifiant d'exécution UUID v4 | Validée ([ADR-0003](decisions/0003-executions-atomiques.md)) |
| 14 | Licence MIT, « Copyright (c) 2026 LUMU BAMANA MANASSE » | Validée ; fichier `LICENSE` créé, identique à celui du service 1 (même empreinte que le fichier publié sur GitHub, titulaire et année confirmés par l'utilisateur) |

### Points fermés

| # | Point | Résolution |
| --- | --- | --- |
| O-2 | Encodage CSV par défaut | UTF-8 sans BOM (décision 12) |
| O-3 | Nom de la commande et du paquet | `data-automate`, `data_automation` (décision 7) |
| O-4 | Format de l'identifiant d'exécution | UUID v4 (décision 13) |
| O-5 | Licence | MIT (décision 14) |
| O-1 | Compatibilité de pydantic, pydantic-core et PyYAML avec Python 3.14 / Windows 11 | **Vérifiée en phase 1** par une installation réelle : pydantic 2.14.1, pydantic-core 2.50.1 (module compilé `cp314-win_amd64` chargé sans blocage par la politique de sécurité Windows), PyYAML 6.0.3 (extension C disponible). Versions figées dans `constraints.txt`. |

### Vérifications restant à faire pendant le développement

Chacune bloque la phase indiquée si elle échoue.

| # | Vérification | Phase |
| --- | --- | --- |
| O-2b | Importer réellement un export CSV dans Power BI Desktop (encodage sans BOM, séparateur décimal avec des paramètres régionaux français). Tant que ce n'est pas fait, la documentation présente ces attentes comme non testées. | **Toujours ouvert en v1.3** : aucun import réel n'a été fait ; `docs/powerbi.md` présente les réglages et la requête Power Query comme non testés. Ne bloque pas le MVP, qui couvre la préparation des fichiers (§8.1). |

---

## 19. Définition de la réussite

Une personne peut, sans modifier le code, configurer un workflow documenté qui consolide
plusieurs fichiers, transforme les données, calcule des indicateurs, produit un fichier
exploitable dans Power BI et génère un rapport fiable de son exécution. Le résultat attendu
n'est pas un script qui fonctionne une fois, mais un **outil réutilisable, extensible,
testable et suffisamment fiable pour automatiser des tâches récurrentes**.

**Fin du cahier des charges — version 1.3.**
