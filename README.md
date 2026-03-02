# PerfectDraft Pro - Home Assistant Integration

Intégration HACS pour la tireuse à bière **PerfectDraft Pro** dans Home Assistant. Interroge l'API cloud PerfectDraft toutes les 60 secondes.

## Fonctionnalités

### Capteurs (sensors)
- Température de la bière (°C)
- Température cible (°C)
- Volume du fût restant (L)
- Pression du fût (kPa)
- Volume du dernier verre (L)
- Durée du dernier verre (ms)
- Nombre de verres servis depuis le démarrage
- Bière en cours (nom)
- Date d'insertion du fût
- Mode de fonctionnement
- Points fidélité
- Niveau fidélité
- Version firmware
- Codes d'erreur

### Capteurs binaires
- Porte fermée
- Connectée au cloud

## Installation via HACS

1. Ouvrir HACS dans Home Assistant
2. Aller dans **Intégrations** → menu `⋮` → **Dépôts personnalisés**
3. Ajouter l'URL de ce dépôt avec la catégorie **Intégration**
4. Rechercher "PerfectDraft Pro" et l'installer
5. Redémarrer Home Assistant

## Configuration

1. Aller dans **Paramètres** → **Appareils et services** → **Ajouter une intégration**
2. Rechercher "PerfectDraft Pro"
3. Saisir l'**email** et le **mot de passe** de votre compte PerfectDraft

L'intégration gère automatiquement le renouvellement des tokens (sans captcha, sans intervention manuelle).

## Licence

MIT
