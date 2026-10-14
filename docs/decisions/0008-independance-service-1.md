# 0008 — Aucune dépendance au service 1 dans le MVP

**Statut :** Acceptée (finalisation de la phase 0)

## Contexte

`python-data-cleaning-toolkit` (service 1) est publié et terminé. Le §7.4 demande de ne pas
réimplémenter ses règles de nettoyage, et le §17 identifie le couplage entre projets comme un
risque.

## Décision

- Le paquet `data_automation` ne dépend pas de `data_cleaning` dans le MVP.
- Il reprend les **méthodes** validées par le service 1 : lecture en texte puis conversion
  explicite, écriture atomique, relecture de vérification, contrôle préalable de toutes les
  sorties, empreinte des sources, statut d'exécution distinct du statut qualité, rapports
  JSON et Markdown, vérificateur indépendant et tests de mutation.
- Les règles de nettoyage détaillées (dates ambiguës, mappings de catégories, quarantaine)
  ne sont pas recopiées. Si un workflow a besoin d'un nettoyage complet, il pourra plus tard
  appeler le service 1 par une étape d'intégration optionnelle, documentée et testée.

## Conséquences

- Les deux dépôts évoluent et se publient indépendamment.
- Une petite part de code d'infrastructure (écriture atomique, empreinte) sera écrite deux
  fois ; c'est un choix assumé pour éviter un couplage prématuré.

## Alternatives écartées

- **Dépendre de `data_cleaning` comme bibliothèque :** réutilisation immédiate, mais couplage
  des versions et du cycle de publication.
- **Bibliothèque commune extraite des deux projets :** pertinente plus tard si une troisième
  utilisation apparaît (service 3).
