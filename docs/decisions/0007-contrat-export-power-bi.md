# 0007 — Contrat d'export CSV/XLSX pour Power BI et métadonnées

**Statut :** Acceptée (finalisation de la phase 0)

## Contexte

« Prêt pour Power BI » doit être vérifiable. Le MVP couvre la préparation de fichiers ; il ne
couvre ni l'intégration à Power BI Service, ni le rafraîchissement des rapports, ni la
création de tableaux de bord.

## Décision

### Export CSV (format recommandé)

- Encodage **UTF-8 sans BOM**.
- Délimiteur `,`, guillemets selon la norme CSV (RFC 4180), fins de ligne `LF`.
- Un seul en-tête ; noms de colonnes uniques et stables, déclarés dans la configuration.
- Dates en **ISO 8601** : `YYYY-MM-DD` ; date et heure `YYYY-MM-DDTHH:MM:SS`, avec le fuseau
  indiqué (`Z` pour UTC) lorsque l'heure est significative.
- Nombres avec le **point** comme séparateur décimal, sans séparateur de milliers ni symbole
  monétaire.
- Valeurs manquantes : cellules vides.
- Identifiants textuels écrits tels quels (zéros initiaux conservés).

### Export XLSX (lorsque le besoin le justifie)

- Une feuille de données nommée, une ligne d'en-tête.
- Nombres en cellules numériques ; dates en cellules de date avec un format d'affichage ISO
  (`yyyy-mm-dd`) ; identifiants et codes en cellules texte.
- Toute valeur texte commençant par `=` reste du texte (jamais une formule).

### Vérification avant succès (CSV et XLSX)

L'export est écrit dans un fichier temporaire, **relu**, puis comparé au jeu de données :
colonnes attendues présentes et dans l'ordre, types logiques conformes, nombre de lignes
identique. Il n'est déplacé à son emplacement final qu'ensuite (ADR-0003).

### Métadonnées

Chaque export est accompagné de `<nom>.metadata.json` :

- identifiant du workflow et **identifiant d'exécution (UUID v4)** ;
- date et heure d'exécution (UTC, ISO 8601) et paramètres d'exécution ;
- sources utilisées (chemin relatif à la racine de travail, empreinte SHA-256) ;
- contrôles effectués et leur résultat ;
- schéma des colonnes : nom, type logique (`string`, `integer`, `decimal`, `date`,
  `datetime`, `boolean`), nullabilité ;
- format du fichier (encodage, délimiteur, séparateur décimal).

## Attentes d'import dans Power BI Desktop

Ce que le format garantit, et ce que l'utilisateur doit savoir. **Aucun de ces points n'a
encore été vérifié dans Power BI Desktop** (le logiciel n'est pas disponible dans
l'environnement de développement) ; la documentation publique les présentera comme des
recommandations non testées tant qu'un import réel n'aura pas été fait.

| Sujet | Attente | Risque non vérifié |
| --- | --- | --- |
| Encodage | Le connecteur Texte/CSV doit lire le fichier en UTF-8 (page de codes 65001). | Sans BOM, la détection automatique de l'encodage peut se tromper ; il faudra alors choisir « 65001 : Unicode (UTF-8) » dans « Origine du fichier » ou préciser `Encoding = 65001` dans Power Query. |
| Séparateur décimal | Les nombres utilisent le point. | Avec des paramètres régionaux français, la détection automatique des types peut lire `12.5` comme du texte ou un autre nombre ; il faudra convertir le type « à l'aide des paramètres régionaux » `en-US` (ou `Table.TransformColumnTypes` avec la culture `en-US`). |
| Dates | ISO 8601, sans ambiguïté jour/mois. | Comportement de la détection automatique non vérifié selon les paramètres régionaux. |
| Types | Le fichier `.metadata.json` documente le type attendu de chaque colonne. | Power BI ne lit pas ce fichier : les types sont appliqués dans Power Query par l'utilisateur ou par sa requête. |
| Rafraîchissement | Le même chemin de sortie est réécrit à chaque exécution (ADR-0003), ce qui permet d'actualiser le même import. | Non testé avec une actualisation réelle ; Power BI Service et les passerelles sont hors périmètre. |

Un exemple de requête Power Query documentant ces réglages sera fourni en phase 4 et marqué
« non testé dans Power BI Desktop » tant qu'aucun import réel n'aura été réalisé.

## Conséquences

- Le format reçu par Power BI est connu et reproductible ; les exports sont vérifiables par
  des tests automatisés.
- Le fichier de métadonnées sert aussi à l'audit (UC-02, NFR-04).
- L'absence de BOM est le format le plus portable, mais peut demander un réglage d'encodage
  dans Power BI : c'est documenté plutôt que caché.

## Alternatives écartées

- **UTF-8 avec BOM :** facilite la détection par Excel et peut-être Power BI, mais gêne
  certains outils et n'a pas été retenu ; il pourra devenir une option de configuration.
- **Parquet dès le MVP :** ajoute une dépendance (pyarrow) ; reporté (§8.2).
- **Export sans contrat explicite :** ne permet pas de vérifier « prêt pour Power BI ».
