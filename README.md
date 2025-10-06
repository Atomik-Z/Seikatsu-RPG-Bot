# Bot Discord RPG - Guide d'Installation et d'Utilisation

## 📋 Description

Ce bot Discord implémente un système de jeu de rôle complet avec :
- Création de personnages avec talents aléatoires
- Système de compétences à 4 catégories 
- Combat en temps réel avec mécaniques avancées
- État de bloodlust et affaiblissement
- Système d'expérience et de niveau
- Base de données SQLite pour la persistance

## 🔧 Installation

### Prérequis

1. **Python 3.8+** installé sur votre système
2. **Compte Discord Développeur** pour créer un bot

### Étapes d'installation

1. **Cloner ou télécharger les fichiers**
   ```bash
   # Téléchargez le fichier discord_rpg_bot_complet.py
   ```

2. **Installer discord.py**
   ```bash
   pip install discord.py
   ```

3. **Créer un bot Discord**
   - Allez sur https://discord.com/developers/applications
   - Cliquez sur "New Application"
   - Donnez un nom à votre application
   - Allez dans l'onglet "Bot"
   - Cliquez sur "Add Bot"
   - Copiez le token du bot

4. **Configurer le bot**
   - Ouvrez le fichier `discord_rpg_bot_complet.py`
   - Remplacez `'VOTRE_TOKEN_ICI'` par le token de votre bot Discord
   ```python
   TOKEN = 'votre_token_discord_ici'
   ```

5. **Inviter le bot sur votre serveur**
   - Dans l'onglet "OAuth2" > "URL Generator"
   - Sélectionnez "bot" dans les scopes
   - Sélectionnez les permissions : "Send Messages", "Read Message History", "Use Slash Commands"
   - Utilisez l'URL générée pour inviter le bot

6. **Lancer le bot**
   ```bash
   python discord_rpg_bot_complet.py
   ```

## 🎮 Guide d'Utilisation

### Commandes de Base

#### Création de Personnage
```
!creer_personnage Nom du Personnage
```
- Crée un nouveau personnage avec un talent aléatoire
- Vous pouvez ensuite créer 2 compétences initiales

#### Consulter ses Personnages
```
!mes_personnages          # Liste tous vos personnages
!stats Nom du Personnage  # Détails d'un personnage
```

### Système de Combat

#### Démarrer un Combat
```
!defier @nom_du_joueur                # Défier un joueur
!choisir_personnage Nom du Personnage # Sélectionner son combattant
!objectif 1                           # Choisir objectif (1=KO, 2=Vider Pouvoir, 3=Bloodlust)
!pfc pierre                           # Pierre-feuille-ciseaux pour l'ordre
```

#### Actions de Combat
```
!attaque                    # Attaque basique (100 dégâts de base)
!competence Nom Compétence  # Utiliser une compétence
!defense                    # Se défendre (-50% dégâts reçus)
!bloodlust                  # Entrer en bloodlust (si jauge vide)
!forfait                    # Abandonner le combat
```

#### Pendant le Combat
```
!mes_competences  # Voir vos compétences et leur statut
```

### Talents et Avantages

Les talents donnent +10%/-10% de dégâts selon les matchups :
- **Yeux de Dieu** > Dieu de la Vitesse > Inégalé > Forteresse > Overpowered > Yeux de Dieu

### Catégories de Compétences

1. **Attaque** : Dégâts x3, coût 10%, cooldown 1 tour
2. **Bonus** : Prochaine attaque +50%, coût 15%, cooldown 2 tours  
3. **Malus** : Prochaine attaque adverse -30%, coût 15%, cooldown 2 tours
4. **Restreinte** : Fait sauter un tour adverse, dégâts x0.8, coût 20%, cooldown 3 tours

### Système d'Expérience

- **Victoire** : +2000 XP
- **Dégâts infligés** : +1 XP par point de dégât
- **PV restants** : +1 XP par PV
- **Multiplicateur** : Basé sur le % de jauge de pouvoir restant

### Commandes Utilitaires

```
!aide                      # Liste toutes les commandes
!aide_combat              # Guide détaillé du combat
!talents                   # Infos sur les talents
!classement niveau         # Top 10 par niveau ou expérience
!statistiques_globales     # Stats du serveur
!ajouter_competence Nom    # Ajouter une compétence (tous les 10 niveaux)
!supprimer_personnage Nom  # Supprimer un personnage
```

### Commandes Administrateur

```
!admin_modifier Nom attribut valeur  # Modifier n'importe quel personnage
```

Attributs modifiables : `hp`, `pv`, `max_hp`, `power_gauge`, `niveau`, `experience`, `talent`

## ⚔️ Mécaniques de Combat Avancées

### État de Bloodlust
- **Activation** : Quand la jauge de pouvoir tombe à 0
- **Effets** : 
  - Dégâts infligés x2
  - Dégâts reçus x2  
  - 30% de chance d'action aléatoire
  - 30% de chance de récupérer 25% des dégâts en PV
- **Durée** : 8 tours + 2 tours d'affaiblissement

### Formule de Dégâts
```
Dégâts = 100 × Talent × Compétence × Bloodlust × Affaibli × Bonus × Défense × Malus
```

Où :
- **Talent** : 1.1 (advantage) / 0.9 (désavantage) / 1.0 (neutre)
- **Compétence** : 3.0 (Attaque) / 0.8 (Restreinte) / 1.0 (autres)
- **Bloodlust** : 2.0 si actif / 1.0 sinon
- **Défense** : 0.5 si en défense / 1.0 sinon

## 📊 Base de Données

Le bot crée automatiquement une base de données SQLite (`discord_rpg.db`) avec :
- Table `characters` : Informations des personnages
- Table `skills` : Compétences des personnages

## 🐛 Dépannage

### Erreurs Communes

1. **"Token invalide"** : Vérifiez que vous avez bien copié le token du bot
2. **"Module discord non trouvé"** : Installez discord.py avec `pip install discord.py`
3. **"Permission denied"** : Le bot n'a pas les permissions nécessaires sur le serveur
4. **"Database locked"** : Redémarrez le bot si la base de données se bloque

### Logs et Debug

Le bot affiche des messages de debug dans la console. En cas d'erreur :
1. Vérifiez les messages d'erreur dans la console
2. Assurez-vous que le bot a les bonnes permissions
3. Redémarrez le bot si nécessaire

## 🔒 Sécurité

- **Ne partagez jamais votre token Discord**
- Le token donne accès complet au bot
- Régénérez le token si vous pensez qu'il a été compromis

## 📝 Notes Importantes

- Un joueur peut avoir plusieurs personnages
- Les noms de personnages sont uniques par joueur
- Les combats sont limités à un par canal
- La base de données conserve toutes les données entre les redémarrages
- Les cooldowns et états sont réinitialisés à chaque combat

## 🆘 Support

Si vous rencontrez des problèmes :
1. Vérifiez ce guide d'abord
2. Assurez-vous d'avoir Python 3.8+ et discord.py installé
3. Vérifiez que le token est correct
4. Redémarrez le bot en cas de problème

## 🎉 Fonctionnalités Avancées

- **Auto-complétion** : Le bot propose des suggestions
- **Gestion d'erreurs** : Messages d'erreur explicites
- **Persistence** : Toutes les données sont sauvegardées
- **Multi-serveur** : Le bot peut fonctionner sur plusieurs serveurs
- **Classements** : Système de classement global
- **Statistics** : Suivi des statistiques globales

Bon jeu ! ⚔️🎭
