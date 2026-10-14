# 0006 — Racine de travail et refus des chemins extérieurs

**Statut :** Acceptée (finalisation de la phase 0)

## Contexte

NFR-05 demande de « limiter les accès aux emplacements autorisés par la configuration ». Un
workflow lit des motifs de fichiers et écrit des sorties ; une faute de frappe ou une
configuration malveillante pourrait viser un autre emplacement (`..\..\`, chemin absolu).

## Décision

- Chaque workflow déclare une **racine de travail** (par défaut : le dossier du fichier de
  configuration). Tous les chemins de la configuration sont relatifs à cette racine.
- Après résolution des paramètres et des motifs, tout chemin qui sort de la racine est
  refusé avant l'exécution (comparaison des chemins résolus, liens symboliques compris).
- Les fichiers sources ne sont jamais ouverts en écriture ; leur empreinte SHA-256 est
  vérifiée avant et après l'exécution (méthode du service 1).
- Une sortie ne peut jamais désigner une source du même workflow.

## Conséquences

- Les erreurs de chemin sont détectées à la validation, pas pendant le traitement.
- Pour lire des données situées ailleurs, il faut déplacer la racine : c'est voulu.
- Test d'acceptation dédié (AC-15).

## Alternatives écartées

- **Liste d'emplacements autorisés multiples :** plus souple, plus complexe ; reportée si un
  cas réel le demande.
- **Aucune restriction :** contraire à NFR-05.
