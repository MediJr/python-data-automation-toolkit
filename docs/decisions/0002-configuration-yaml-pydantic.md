# 0002 — Configuration YAML chargée en mode sûr, validée par Pydantic

**Statut :** Acceptée (revue de phase 0)

## Contexte

Un workflow est une structure imbriquée (sources, étapes typées avec leurs paramètres,
sorties, politique d'erreur). Le §6.2 exige une validation complète avant exécution avec des
messages précis. Le service 1 utilise JSON validé par du code maison, ce qui reste
raisonnable pour une configuration plate, mais devient coûteux pour des étapes typées.

## Décision

- Fichiers de workflow en YAML, chargés **uniquement** avec `yaml.safe_load` (PyYAML).
- Validation par des modèles Pydantic : clés inconnues interdites, types stricts, un modèle
  de paramètres par type d'étape (union discriminée sur `type`).
- Vérifications croisées après Pydantic : entrées d'étape produites en amont, identifiants
  uniques, chemins dans la racine de travail, paramètres obligatoires fournis.

## Conséquences

- Deux dépendances : PyYAML et Pydantic (avec pydantic-core, compilé). Installation
  vérifiée en phase 1 sur Python 3.14 / Windows 11 : pydantic 2.14.1, pydantic-core 2.50.1,
  PyYAML 6.0.3 (point O-1 fermé).
- En phase 1, le chargeur refuse aussi les clés en double et les ancres/alias YAML : PyYAML
  conserverait sinon silencieusement la dernière valeur d'une clé répétée.
- Les balises YAML d'exécution (`!!python/object` …) sont refusées par construction ; un test
  le démontrera (AC-15).
- Les messages d'erreur Pydantic seront reformulés pour l'utilisateur (chemin de la clé,
  valeur reçue, valeur attendue).

## Alternatives écartées

- **JSON + validation maison :** aucune dépendance, mais configurations moins lisibles et
  validation plus longue à écrire pour des étapes typées.
- **YAML + jsonschema :** possible, mais messages d'erreur moins précis et modèles moins
  réutilisables dans le code.
