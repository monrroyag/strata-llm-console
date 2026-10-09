# Strata LLM Console — Français

[English](README.en.md) · [Español](README.es.md) · [Português](README.pt.md) · [Français](README.fr.md) · [Deutsch](README.de.md)

L’anglais est la langue initiale et la documentation de référence de Strata LLM Console. La langue peut être changée dans l’en-tête ou les préférences.

## Origine du moteur

Cette console est une couche opérationnelle pour le [moteur officiel d’inférence Strata](https://github.com/Niko1221/Strata). Le dépôt d’origine est `https://github.com/Niko1221/Strata.git`. La console gère le catalogue, les paramètres, le cycle de vie, l’exposition réseau, l’observabilité et les mises à jour.

## Sections principales

- **Opérer** — enregistrer, sélectionner, charger, décharger, arrêter et retirer les modèles; modifier les paramètres; analyser la mémoire et le contexte.
- **Observer** — consulter la VRAM/RAM, les performances historiques, les traces, le raisonnement émis par le moteur, les outils, les tokens, la latence et les erreurs.
- **Connecter** — conserver l’API en local, activer le LAN explicitement, configurer Bearer/CORS et utiliser un tunnel chiffré.
- **Système** — vérifier la version de Strata, rechercher les mises à jour, détecter les backends et personnaliser l’interface.

## API

- Passerelle OpenAI : `http://127.0.0.1:8090/v1`
- API de contrôle : `http://127.0.0.1:8090/api`
- L’accès distant exige `Authorization: Bearer <console-token>`.
- L’adresse par défaut est loopback; le LAN et CORS sont opt-in.

## Optimiseur

Il combine la mémoire GPU/RAM réelle, le contexte demandé, la quantification KV, le cache d’experts, les réglages MTP/lookup, la configuration actuelle, l’historique et les marges de risque. Il renvoie une recommandation, des alternatives et un niveau de confiance. L’analyse statique est indiquée clairement et n’est pas présentée comme un benchmark.

## Telegram

Le bot avec liste autorisée contrôle l’état, la sélection des modèles, l’arrêt, le déchargement, les confirmations, les traces, les erreurs, l’optimisation, la connexion et les mises à jour Strata. Les nouveaux chats commencent en anglais et peuvent choisir une autre langue.

## Captures

![Navigation groupée](../screenshots/models-grouped-en-final2.png)
![Performances](../screenshots/performance.png)
![Traces](../screenshots/traces-errors.png)
![Connexion](../screenshots/connection-final.png)
![Préférences](../screenshots/preferences-latest.png)
![Paramètres](../screenshots/parameters.png)
![Optimiseur](../screenshots/optimizer-analysis.png)
![Mises à jour](../screenshots/update.png)
![Tunnel](../screenshots/tunnel.png)
![Ajout d’un modèle](../screenshots/add.png)
![Activité](../screenshots/activity.png)

## Installation Linux

Après la publication d’une version, installez le paquet Linux pour l’utilisateur avec :

```bash
curl -fsSL https://github.com/monrroyag/strata-llm-console/releases/latest/download/install-linux.sh | bash
```

L’installateur vérifie SHA-256, installe dans `~/.local/share/strata-llm-console`, crée la commande dans `~/.local/bin` et enregistre un service systemd utilisateur si disponible.

## Sécurité du dépôt

Les tokens, fichiers d’environnement, traces, logs, GGUF, packs, binaires et chemins propres à la machine restent hors de Git. Retirer un modèle du catalogue ne supprime jamais ses fichiers originaux.