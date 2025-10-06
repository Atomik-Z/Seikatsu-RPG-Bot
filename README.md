# Bot Discord RPG avec Commandes Slash - Guide d'Installation et d'Utilisation

## 📋 Description

Ce bot Discord implémente un système de jeu de rôle complet utilisant **uniquement des commandes slash (/)** pour une interface moderne et intuitive. Le système inclut :

- 🎭 Création de personnages avec talents aléatoires
- ⚔️ Système de combat interactif avec boutons
- 🎪 4 catégories de compétences avec mécaniques uniques
- 🔥 État de bloodlust et système d'affaiblissement
- 📈 Progression par expérience et niveaux
- 🗄️ Base de données SQLite pour la persistance
- 🎮 Interface utilisateur moderne avec Select Menus et boutons

## 🔧 Installation

### Prérequis

1. **Python 3.8+** installé sur votre système
2. **py-cord** (version moderne de discord.py)
3. **Compte Discord Développeur** pour créer un bot

### Étapes d'installation

1. **Installer py-cord** (version qui supporte les slash commands)
   ```bash
   pip install py-cord
   ```

2. **Créer un bot Discord**
   - Allez sur https://discord.com/developers/applications
   - Cliquez sur "New Application"
   - Donnez un nom à votre application
   - Allez dans l'onglet "Bot"
   - Cliquez sur "Add Bot"
   - Copiez le token du bot
   - **IMPORTANT** : Activez les "Message Content Intent" si nécessaire

3. **Configurer le bot**
   - Ouvrez le fichier `discord_rpg_bot_slash_commands.py`
   - Remplacez `'VOTRE_TOKEN_ICI'` par le token de votre bot Discord
   ```python
   TOKEN = 'votre_token_discord_ici'
   ```

4. **Inviter le bot sur votre serveur**
   - Dans l'onglet "OAuth2" > "URL Generator"
   - Sélectionnez "bot" et "applications.commands" dans les scopes
   - Sélectionnez les permissions nécessaires
   - Utilisez l'URL générée pour inviter le bot

5. **Lancer le bot**
   ```bash
   python discord_rpg_bot_slash_commands.py
   ```

## 🎮 Guide d'Utilisation - Commandes Slash

### Commandes de Base

#### Création de Personnage
```
/creer_personnage nom_complet: Nom du Personnage
```
- Crée un nouveau personnage avec un talent aléatoire
- Interface interactive avec Select Menus pour choisir les catégories de compétences
- Création de 2 compétences initiales via dialogue

#### Consulter ses Personnages
```
/mes_personnages          # Liste tous vos personnages
/stats nom_personnage: Nom du Personnage  # Détails d'un personnage
```

### Système de Combat Interactif

#### Démarrer un Combat
```
/defier opponent: @nom_du_joueur                # Défier un joueur
/choisir_personnage nom_personnage: Nom du Personnage # Sélectionner son combattant
```

#### Interface de Combat Moderne
- **Select Menus** pour choisir les objectifs de victoire :
  - 🎯 K.O. - Faire tomber l'adversaire KO (PV à 0)
  - ⚡ Vider Pouvoir - Forcer l'adversaire à vider sa jauge de pouvoir
  - 🔥 Bloodlust - Forcer l'adversaire à consommer son état de bloodlust

- **Select Menus** pour le Pierre-Feuille-Ciseaux :
  - 🪨 Pierre
  - 📄 Feuille  
  - ✂️ Ciseaux

#### Actions de Combat via Boutons
Une fois le combat commencé, utilisez les **boutons interactifs** :

- 🗡️ **Attaque** - Attaque basique (100 dégâts de base)
- 🛡️ **Défense** - Se défendre (-50% dégâts reçus, cooldown)
- 🔥 **Bloodlust** - Entrer en bloodlust (si jauge vide)
- 🏳️ **Forfait** - Abandonner le combat

#### Utiliser les Compétences
```
/competence nom_competence: Nom de la Compétence
```

### Commandes Utilitaires

```
/aide                           # Liste toutes les commandes slash
/classement critere: niveau     # Top 10 par niveau ou expérience
```

## ⚡ Avantages des Commandes Slash

### Interface Moderne
- **Auto-complétion** : Discord suggère automatiquement les paramètres
- **Validation en temps réel** : Les paramètres sont vérifiés avant envoi
- **Interface unifiée** : Même expérience sur tous les clients Discord
- **Pas de préfixe** : Plus besoin de se rappeler du préfixe `!`

### Interactions Avancées
- **Select Menus** pour les choix multiples
- **Boutons** pour les actions de combat
- **Ephemeral responses** pour les messages privés
- **Followup messages** pour les dialogues complexes

### Expérience Utilisateur Améliorée
- **Découvrabilité** : Les commandes apparaissent automatiquement en tapant `/`
- **Hints visuels** : Descriptions et paramètres visibles
- **Réduction d'erreurs** : Validation automatique des entrées
- **Interface tactile** : Parfait pour les utilisateurs mobiles

## 🎯 Nouvelles Fonctionnalités Interactives

### Création de Personnage Guidée
1. Utilisez `/creer_personnage`
2. Le système vous guide avec des menus déroulants
3. Sélectionnez les catégories de compétences via Select Menu
4. Interface claire avec descriptions détaillées

### Combat Immersif
1. Défiez avec `/defier @joueur`
2. Choisissez vos personnages et objectifs via menus
3. Pierre-feuille-ciseaux interactif 
4. Combat en temps réel avec boutons d'action
5. Statut visual du combat mis à jour automatiquement

### Gestion des États
- **États temporaires** affichés visuellement
- **Cooldowns** indiqués clairement
- **Boutons désactivés** quand les actions ne sont pas disponibles
- **Messages éphémères** pour les erreurs privées

## 🔧 Configuration Technique

### Différences avec l'Ancienne Version
```python
# Ancienne version (prefix commands)
@bot.command(name='stats')
async def show_stats(ctx, *, nom_personnage: str):
    # ...

# Nouvelle version (slash commands)
@bot.slash_command(name="stats", description="Afficher les statistiques d'un personnage")
async def show_stats(ctx, nom_personnage: str):
    # ...
```

### Nouveaux Composants UI
- **discord.ui.Select** pour les menus déroulants
- **discord.ui.Button** pour les actions rapides
- **discord.ui.View** pour grouper les composants
- **ctx.respond()** et **ctx.followup** pour les réponses

### Gestion des Permissions
Les commandes slash nécessitent le scope `applications.commands` lors de l'invitation du bot.

## 📊 Système de Combat Inchangé

Toutes les mécaniques de jeu restent identiques :
- Formule de dégâts complexe
- Système de talents avec avantages/désavantages
- 4 catégories de compétences avec effets uniques
- État de bloodlust avec ses 8 tours + affaiblissement
- Calcul d'expérience basé sur performance

## 🐛 Dépannage Spécifique aux Slash Commands

### Erreurs Communes

1. **"Application did not respond"** : Le bot met trop de temps à répondre
   - Utilisez `ctx.defer()` pour les opérations longues
   - Répondez avec `ctx.followup` après defer

2. **"Unknown interaction"** : Token expiré ou bot redémarré
   - Les interactions ont une durée de vie limitée
   - Redémarrez le bot si nécessaire

3. **"Missing Access"** : Permissions insuffisantes
   - Vérifiez que le bot a le scope `applications.commands`
   - Réinvitez le bot avec les bonnes permissions

### Synchronisation des Commandes
Les commandes slash peuvent prendre jusqu'à 1 heure pour apparaître globalement. Pour un développement plus rapide, synchronisez sur un serveur spécifique.

## 🔒 Sécurité et Performance

### Avantages Sécuritaires
- **Validation intégrée** : Discord valide automatiquement les paramètres
- **Pas d'injection** : Les paramètres sont typés et sécurisés
- **Rate limiting** intégré par Discord

### Performance Optimisée
- **Moins de parsing** : Discord gère l'analyse des commandes
- **Réponses cachées** : Utilisation d'ephemeral pour réduire le spam
- **UI components** : Réduit le nombre de messages

## 🆕 Migration depuis la Version Prefix

Si vous utilisez l'ancienne version avec `!` :

1. **Sauvegardez votre base de données** : `discord_rpg.db` reste compatible
2. **Remplacez le fichier Python** par la version slash commands
3. **Réinvitez le bot** avec les nouveaux scopes
4. **Testez les commandes** avec `/` au lieu de `!`

## 🎉 Avantages de Cette Version

✅ **Interface moderne** avec composants UI Discord
✅ **Expérience utilisateur supérieure** 
✅ **Auto-complétion et validation**
✅ **Compatible mobile** et desktop
✅ **Réduction des erreurs utilisateur**
✅ **Découvrabilité améliorée des commandes**
✅ **Interactions tactiles** intuitives
✅ **Messages éphémères** pour moins de pollution

Cette version slash commands offre la même profondeur de jeu avec une interface modernisée et intuitive ! ⚔️🎮
