# 0009 — Choix de réalisation des phases 2 à 6

**Statut :** Acceptée (phases 2 à 6)

## Contexte

Les décisions 0001 à 0008 fixent le périmètre et les principes. En les réalisant, plusieurs
points de détail ont dû être tranchés. Aucun ne modifie le périmètre du MVP ni une décision
acceptée ; ils sont regroupés ici pour que le code, la documentation et le cahier des
charges restent cohérents.

## Décisions

### Exécution (ADR-0003, ADR-0004)

- **Dossier d'exécution :** chaque exécution écrit ses rapports dans
  `<report.directory>/<identifiant du workflow>/<identifiant d'exécution>/` (par défaut
  `runs/…`) : `run_report.json`, `run_report.md`, `run.log` et, si configurée,
  `summary.md`. Les sorties restent à leur emplacement fixe (ADR-0003, alternative écartée
  « un dossier par exécution » pour les sorties), seuls les rapports sont séparés.
- **Verrou :** un fichier `.lock` créé de façon exclusive (`O_EXCL`) dans le dossier du
  workflow empêche deux exécutions simultanées du même workflow. Il n'est jamais supprimé
  automatiquement s'il reste après un arrêt brutal : le message indique le fichier à
  supprimer. Un verrou « périmé » détecté automatiquement aurait pu laisser passer deux
  exécutions réelles.
- **Codes de sortie :** 0 succès, 1 échec, 2 usage, 3 refus avant exécution, **4 exécution
  partielle** (`on_error: continue`) et **130 interruption** (Ctrl+C), en plus de ceux
  prévus en phase 1.
- **Politique `continue` :** les sorties dont le jeu de données a été produit sont vérifiées
  et publiées ; le statut est « partiel » (au moins une sortie publiée) ou « échec ». C'est
  la conséquence prévue par l'ADR-0003 (ensemble mixte signalé dans le rapport).
- **Sources modifiées pendant l'exécution :** l'empreinte SHA-256 est recalculée avant la
  publication ; si une source a changé, rien n'est publié, quelle que soit la politique.

### Configuration (ADR-0002, ADR-0005)

- **Clés YAML non textuelles refusées :** YAML 1.1 lit `on`, `yes`, `no` comme des
  booléens. La jointure aurait naturellement utilisé une clé `on` ; elle utilise donc
  `keys` (ou `left_keys` / `right_keys`), et le chargeur refuse toute clé qui n'est pas un
  texte, avec un message demandant de la mettre entre guillemets.
- **Paramètres dans les filtres (FR-19) :** une condition peut utiliser `param: nom` à la
  place de `value:`. La valeur est lue par son nom dans les paramètres d'exécution et
  convertie au type de la colonne comme une valeur littérale ; aucun texte n'est substitué
  ni évalué. Seuls les opérateurs à valeur unique l'acceptent ; un paramètre non déclaré
  est une erreur de validation.
- **Types de colonnes déclarés à la lecture :** `types` sur une entrée (`string`,
  `integer`, `decimal`, `date`, `datetime`, `boolean`) et `decimal_separator`. Une valeur
  invalide fait échouer la lecture ; rien n'est deviné.
- **Rapport :** `report.directory` et `report.summary` (synthèse métier) complètent
  `report.formats`.

### Données et exports (ADR-0007)

- **Décimaux exacts :** les valeurs `decimal` sont des `Decimal` Python de la lecture à
  l'export ; les sommes sont exactes, `round` arrondit au demi supérieur.
- **Un fichier = une partie :** une entrée à plusieurs fichiers est un jeu de données à
  plusieurs parties ; seule l'étape `concatenate` les combine, ce qui conserve l'origine de
  chaque ligne et détecte les colonnes propres à un fichier.
- **XLSX :** les nombres qu'un nombre Excel (double) ne peut pas représenter exactement
  font échouer l'export au lieu d'être arrondis. À la lecture, les nombres sont convertis en
  texte sans exposant avec le séparateur décimal de l'entrée. Les zéros finaux d'un nombre
  Excel ne sont pas conservés (`250.00` devient `250`), ce qui est documenté.
- **defusedxml :** ajouté comme dépendance d'exécution. Les classeurs XLSX sont des
  données non fiables ; openpyxl l'utilise automatiquement lorsqu'il est installé, et
  l'inspection des formules du toolkit l'utilise directement.

### Code et dépôt (C-14)

- **Modules :** l'`io.py` prévu au §12 est remplacé par `readers.py` et `writers.py`, et les
  paramètres, chemins, types, jeux de données et le chargeur YAML ont chacun leur module.
  Les types d'étapes sont dans le sous-paquet `steps/`.
- **Benchmark :** dans `benchmarks/` ; la méthode de mesure de la mémoire (Job Object
  Windows) est reprise du service 1 par copie, sans dépendance (ADR-0008).

## Conséquences

- Le cahier des charges passe en version 1.3 (changement C-23) et renvoie à cette décision.
- Les points ci-dessus sont testés (voir `docs/testing.md`) et documentés en anglais dans
  `docs/`.
- L'import réel dans Power BI Desktop (point O-2b) reste **non vérifié** : la
  documentation le présente comme tel.

## Alternatives écartées

- **Substituer `{param}` dans le texte des valeurs de filtre :** plus court à écrire, mais
  ambigu pour une valeur qui contient des accolades et proche d'une évaluation de texte.
- **Suppression automatique d'un verrou ancien :** risque de deux exécutions concurrentes.
- **Arrondir silencieusement les décimaux trop longs en XLSX :** contraire au contrat de
  vérification (la relecture aurait comparé des valeurs déjà arrondies).
