
import discord
from discord.ext import commands
import random
import sqlite3
import asyncio
import json
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Configuration du bot
TOKEN = os.environ.get('DISCORD_TOKEN')  # Remplacez par votre token Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Enums et classes de données
class SkillCategory(Enum):
    ATTAQUE = "Attaque"
    BONUS = "Bonus"
    MALUS = "Malus"
    RESTREINTE = "Restreinte"

class Talent(Enum):
    DIEU_VITESSE = "Dieu de la Vitesse"
    INEGALE = "Inégalé"
    FORTERESSE = "Forteresse"
    OVERPOWERED = "Overpowered"
    YEUX_DIEU = "Yeux de Dieu"

class CombatAction(Enum):
    ATTAQUE_BASIQUE = "Attaque Basique"
    COMPETENCE = "Compétence"
    DEFENSE = "Défense"

class ObjectifVictoire(Enum):
    KO = "Faire tomber l'adversaire KO"
    VIDER_POUVOIR = "Vider la jauge de pouvoir"
    CONSOMMER_BLOODLUST = "Consommer l'état de bloodlust"

@dataclass
class Skill:
    name: str
    effect: str
    category: SkillCategory
    cooldown: int = 0  # Cooldown actuel en combat

    def get_power_cost(self) -> float:
        costs = {
            SkillCategory.ATTAQUE: 10.0,
            SkillCategory.BONUS: 15.0,
            SkillCategory.MALUS: 15.0,
            SkillCategory.RESTREINTE: 20.0
        }
        return costs[self.category]

    def get_cooldown_duration(self) -> int:
        durations = {
            SkillCategory.ATTAQUE: 1,
            SkillCategory.BONUS: 2,
            SkillCategory.MALUS: 2,
            SkillCategory.RESTREINTE: 3
        }
        return durations[self.category]

@dataclass
class Character:
    name: str
    owner_id: int
    hp: int = 1000
    max_hp: int = 1000
    power_gauge: float = 100.0
    talent: Talent = None
    level: int = 1
    experience: int = 0
    skills: List[Skill] = None

    # États de combat
    defending: bool = False
    defense_cooldown: int = 0
    bonus_next_attack: float = 1.0
    malus_next_received: float = 1.0
    bloodlust_turns: int = 0
    weakened_turns: int = 0
    skip_next_turn: bool = False
    was_in_bloodlust: bool = False

    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        if self.talent is None:
            self.talent = random.choice(list(Talent))

    def can_level_up(self) -> bool:
        return self.experience >= self.get_level_threshold()

    def get_level_threshold(self) -> int:
        if self.level == 1:
            return 5000
        threshold = 5000
        for i in range(2, self.level + 1):
            threshold += 200 * (i - 1)
        return threshold

    def level_up(self):
        while self.can_level_up():
            threshold = self.get_level_threshold()
            overflow = self.experience - threshold
            self.experience = overflow
            self.level += 1

    def get_talent_advantage(self, opponent_talent: Talent) -> float:
        # Yeux de Dieu > Dieu de la Vitesse > Inégalé > Forteresse > Overpowered > Yeux de Dieu
        advantages = {
            (Talent.YEUX_DIEU, Talent.DIEU_VITESSE): 1.1,
            (Talent.DIEU_VITESSE, Talent.INEGALE): 1.1,
            (Talent.INEGALE, Talent.FORTERESSE): 1.1,
            (Talent.FORTERESSE, Talent.OVERPOWERED): 1.1,
            (Talent.OVERPOWERED, Talent.YEUX_DIEU): 1.1
        }

        if (self.talent, opponent_talent) in advantages:
            return 1.1
        elif (opponent_talent, self.talent) in advantages:
            return 0.9
        else:
            return 1.0

# Classes pour gérer les combats
class CombatSession:
    def __init__(self, player1_id: int, player2_id: int, channel_id: int):
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.channel_id = channel_id
        self.player1_character = None
        self.player2_character = None
        self.player1_objective = None
        self.player2_objective = None
        self.current_turn = None
        self.turn_count = 0
        self.rps_results = {}  # Résultats pierre-feuille-ciseaux
        self.combat_started = False

    def both_players_ready(self) -> bool:
        return (self.player1_character is not None and 
                self.player2_character is not None and
                self.player1_objective is not None and
                self.player2_objective is not None)

    def get_opponent_id(self, player_id: int) -> int:
        return self.player2_id if player_id == self.player1_id else self.player1_id

    def get_character(self, player_id: int) -> Character:
        return self.player1_character if player_id == self.player1_id else self.player2_character

    def get_opponent_character(self, player_id: int) -> Character:
        return self.player2_character if player_id == self.player1_id else self.player1_character

# Système de base de données
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('discord_rpg.db')
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Table des personnages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                hp INTEGER DEFAULT 1000,
                max_hp INTEGER DEFAULT 1000,
                power_gauge REAL DEFAULT 100.0,
                talent TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                UNIQUE(name, owner_id)
            )
        """)

        # Table des compétences
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                effect TEXT NOT NULL,
                category TEXT NOT NULL,
                FOREIGN KEY (character_id) REFERENCES characters (id)
            )
        """)

        self.conn.commit()

    def save_character(self, character: Character) -> int:
        cursor = self.conn.cursor()

        try:
            # Sauvegarder le personnage
            cursor.execute("""
                INSERT INTO characters (name, owner_id, hp, max_hp, power_gauge, talent, level, experience)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (character.name, character.owner_id, character.hp, character.max_hp, 
                  character.power_gauge, character.talent.value, character.level, character.experience))

            character_id = cursor.lastrowid

            # Sauvegarder les compétences
            for skill in character.skills:
                cursor.execute("""
                    INSERT INTO skills (character_id, name, effect, category)
                    VALUES (?, ?, ?, ?)
                """, (character_id, skill.name, skill.effect, skill.category.value))

            self.conn.commit()
            return character_id
        except sqlite3.IntegrityError:
            return None

    def update_character(self, character: Character):
        cursor = self.conn.cursor()

        # Mettre à jour le personnage
        cursor.execute("""
            UPDATE characters 
            SET hp = ?, max_hp = ?, power_gauge = ?, talent = ?, level = ?, experience = ?
            WHERE name = ? AND owner_id = ?
        """, (character.hp, character.max_hp, character.power_gauge, character.talent.value, 
              character.level, character.experience, character.name, character.owner_id))

        # Récupérer l'ID du personnage
        cursor.execute("SELECT id FROM characters WHERE name = ? AND owner_id = ?", 
                      (character.name, character.owner_id))
        char_id = cursor.fetchone()[0]

        # Supprimer les anciennes compétences
        cursor.execute("DELETE FROM skills WHERE character_id = ?", (char_id,))

        # Ajouter les nouvelles compétences
        for skill in character.skills:
            cursor.execute("""
                INSERT INTO skills (character_id, name, effect, category)
                VALUES (?, ?, ?, ?)
            """, (char_id, skill.name, skill.effect, skill.category.value))

        self.conn.commit()

    def get_character(self, name: str, owner_id: int) -> Optional[Character]:
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM characters WHERE name = ? AND owner_id = ?
        """, (name, owner_id))

        char_data = cursor.fetchone()
        if not char_data:
            return None

        # Récupérer les compétences
        cursor.execute("""
            SELECT name, effect, category FROM skills WHERE character_id = ?
        """, (char_data[0],))

        skills_data = cursor.fetchall()
        skills = [Skill(name=s[0], effect=s[1], category=SkillCategory(s[2])) 
                 for s in skills_data]

        return Character(
            name=char_data[1],
            owner_id=char_data[2],
            hp=char_data[3],
            max_hp=char_data[4],
            power_gauge=char_data[5],
            talent=Talent(char_data[6]),
            level=char_data[7],
            experience=char_data[8],
            skills=skills
        )

    def get_character_by_name_any_owner(self, name: str) -> Optional[Character]:
        cursor = self.conn.cursor()

        cursor.execute("SELECT * FROM characters WHERE name = ?", (name,))

        char_data = cursor.fetchone()
        if not char_data:
            return None

        # Récupérer les compétences
        cursor.execute("""
            SELECT name, effect, category FROM skills WHERE character_id = ?
        """, (char_data[0],))

        skills_data = cursor.fetchall()
        skills = [Skill(name=s[0], effect=s[1], category=SkillCategory(s[2])) 
                 for s in skills_data]

        return Character(
            name=char_data[1],
            owner_id=char_data[2],
            hp=char_data[3],
            max_hp=char_data[4],
            power_gauge=char_data[5],
            talent=Talent(char_data[6]),
            level=char_data[7],
            experience=char_data[8],
            skills=skills
        )

    def get_all_characters(self, owner_id: int) -> List[Character]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM characters WHERE owner_id = ?", (owner_id,))

        characters = []
        for char_data in cursor.fetchall():
            # Récupérer les compétences pour chaque personnage
            cursor.execute("""
                SELECT name, effect, category FROM skills WHERE character_id = ?
            """, (char_data[0],))

            skills_data = cursor.fetchall()
            skills = [Skill(name=s[0], effect=s[1], category=SkillCategory(s[2])) 
                     for s in skills_data]

            character = Character(
                name=char_data[1],
                owner_id=char_data[2],
                hp=char_data[3],
                max_hp=char_data[4],
                power_gauge=char_data[5],
                talent=Talent(char_data[6]),
                level=char_data[7],
                experience=char_data[8],
                skills=skills
            )
            characters.append(character)

        return characters

    def delete_character(self, name: str, owner_id: int):
        cursor = self.conn.cursor()

        # Récupérer l'ID du personnage
        cursor.execute("SELECT id FROM characters WHERE name = ? AND owner_id = ?", 
                      (name, owner_id))
        char_data = cursor.fetchone()
        if char_data:
            char_id = char_data[0]
            # Supprimer les compétences
            cursor.execute("DELETE FROM skills WHERE character_id = ?", (char_id,))
            # Supprimer le personnage
            cursor.execute("DELETE FROM characters WHERE id = ?", (char_id,))
            self.conn.commit()

# Système de combat
class CombatSystem:
    def __init__(self):
        self.active_combats = {}  # channel_id -> CombatSession
        self.pending_combats = {}  # player_id -> channel_id

    def calculate_damage(self, attacker: Character, defender: Character, 
                        is_skill: bool = False, skill_category: SkillCategory = None) -> int:
        base_damage = 100

        # Avantage/désavantage de talent
        talent_modifier = attacker.get_talent_advantage(defender.talent)

        # Modificateur de compétence
        skill_modifier = 1.0
        if is_skill:
            if skill_category == SkillCategory.ATTAQUE:
                skill_modifier = 1.5
            elif skill_category == SkillCategory.RESTREINTE:
                skill_modifier = 0.8

        # État de bloodlust
        bloodlust_modifier = 2.0 if attacker.bloodlust_turns > 0 else 1.0

        # État affaibli
        weakened_modifier = 0.5 if attacker.weakened_turns > 0 else 1.0

        # Bonus d'attaque
        bonus_modifier = attacker.bonus_next_attack

        # Défense de l'adversaire
        defense_modifier = 0.5 if defender.defending else 1.0

        # Malus reçu
        malus_modifier = defender.malus_next_received

        # Calcul final
        damage = (base_damage * talent_modifier * skill_modifier * 
                 bloodlust_modifier * weakened_modifier * bonus_modifier * 
                 defense_modifier * malus_modifier)

        # Appliquer le modificateur de bloodlust pour les dégâts reçus
        if defender.bloodlust_turns > 0:
            damage *= 2.0
        elif defender.weakened_turns > 0:
            damage *= 2.0

        return int(damage)

    def use_skill(self, character: Character, skill: Skill, opponent: Character) -> bool:
        # Vérifier si la compétence est en cooldown
        if skill.cooldown > 0:
            return False

        # Vérifier si le personnage a assez de jauge de pouvoir
        if character.power_gauge < skill.get_power_cost():
            return False

        # Consommer la jauge de pouvoir
        character.power_gauge -= skill.get_power_cost()

        # Appliquer les effets selon la catégorie
        if skill.category == SkillCategory.BONUS:
            character.bonus_next_attack = 1.3  # +30% de dégâts à la prochaine attaque
        elif skill.category == SkillCategory.MALUS:
            opponent.malus_next_received = 0.7  # -30% de dégâts à la prochaine attaque reçue
        elif skill.category == SkillCategory.RESTREINTE:
            opponent.skip_next_turn = True

        # Démarrer le cooldown
        skill.cooldown = skill.get_cooldown_duration()

        return True

    def process_turn_end(self, character: Character):
        """Traiter les effets de fin de tour"""
        # Réduire les cooldowns
        for skill in character.skills:
            if skill.cooldown > 0:
                skill.cooldown -= 1

        # Réduire le cooldown de défense
        if character.defense_cooldown > 0:
            character.defense_cooldown -= 1

        # Réinitialiser les modificateurs temporaires
        character.bonus_next_attack = 1.0
        character.malus_next_received = 1.0
        character.defending = False

        # Gérer l'état de bloodlust
        if character.bloodlust_turns > 0:
            character.bloodlust_turns -= 1
            if character.bloodlust_turns == 0:
                character.weakened_turns = 2  # Commence l'état affaibli

        # Gérer l'état affaibli
        if character.weakened_turns > 0:
            character.weakened_turns -= 1

    def check_victory_conditions(self, session: CombatSession) -> Optional[int]:
        """Vérifier les conditions de victoire, retourne l'ID du gagnant ou None"""
        char1 = session.player1_character
        char2 = session.player2_character
        obj1 = session.player1_objective
        obj2 = session.player2_objective

        # Vérifier KO
        if char1.hp <= 0:
            if obj2 == ObjectifVictoire.KO:
                return session.player2_id
            # Si ce n'est pas l'objectif, le personnage peut entrer en bloodlust
            return None

        if char2.hp <= 0:
            if obj1 == ObjectifVictoire.KO:
                return session.player1_id
            return None

        # Vérifier jauge de pouvoir vide
        if char1.power_gauge <= 0:
            if obj2 == ObjectifVictoire.VIDER_POUVOIR:
                return session.player2_id
            return None

        if char2.power_gauge <= 0:
            if obj1 == ObjectifVictoire.VIDER_POUVOIR:
                return session.player1_id
            return None

        # Vérifier fin de bloodlust
        if (char1.bloodlust_turns == 0 and char1.weakened_turns == 0 and 
            char1.was_in_bloodlust):
            if obj2 == ObjectifVictoire.CONSOMMER_BLOODLUST:
                return session.player2_id

        if (char2.bloodlust_turns == 0 and char2.weakened_turns == 0 and 
            char2.was_in_bloodlust):
            if obj1 == ObjectifVictoire.CONSOMMER_BLOODLUST:
                return session.player1_id

        return None

    def calculate_experience(self, character: Character, damage_dealt: int, 
                           victory: bool, final_hp: int, final_power: float) -> int:
        """Calculer l'expérience gagnée après un combat"""
        base_exp = 0

        # Objectif réussi
        if victory:
            base_exp += 2000

        # Dégâts infligés
        base_exp += damage_dealt

        # PV restants
        base_exp += final_hp

        # Multiplicateur de jauge de pouvoir
        power_multiplier = 1.0 + (final_power / 100.0)

        return int(base_exp * power_multiplier)

# Instances globales
db = Database()
combat_system = CombatSystem()

# ========== COMMANDES DU BOT ==========

@bot.event
async def on_ready():
    print(f'{bot.user} est connecté et prêt!')
    print(f'Bot actif sur {len(bot.guilds)} serveur(s)')
    await bot.change_presence(activity=discord.Game(name="RPG Discord | !aide"))

@bot.command(name='creer_personnage', aliases=['cp'])
async def create_character(ctx, *, nom_complet: str):
    """Créer un nouveau personnage"""

    # Vérifier si le personnage existe déjà
    existing_char = db.get_character(nom_complet, ctx.author.id)
    if existing_char:
        await ctx.send(f"Vous avez déjà un personnage nommé **{nom_complet}**!")
        return

    # Créer le personnage
    character = Character(
        name=nom_complet,
        owner_id=ctx.author.id
    )

    embed = discord.Embed(
        title="🎭 Création de Personnage",
        description=f"Personnage **{nom_complet}** créé!",
        color=0x00ff00
    )
    embed.add_field(name="Talent", value=character.talent.value, inline=True)
    embed.add_field(name="PV", value=f"{character.hp}/{character.max_hp}", inline=True)
    embed.add_field(name="Niveau", value=character.level, inline=True)

    await ctx.send(embed=embed)

    # Processus de création des compétences
    await ctx.send("Vous pouvez maintenant créer **2 compétences** pour votre personnage.")

    for i in range(2):
        await ctx.send(f"**Compétence {i+1}/2**")

        # Demander le nom de la compétence
        await ctx.send("Entrez le nom de la compétence:")
        try:
            name_msg = await bot.wait_for('message', 
                                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                        timeout=60.0)
            skill_name = name_msg.content
        except asyncio.TimeoutError:
            await ctx.send("Temps écoulé. Création annulée.")
            return

        # Demander l'effet de la compétence
        await ctx.send("Entrez l'effet de la compétence:")
        try:
            effect_msg = await bot.wait_for('message',
                                          check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                          timeout=60.0)
            skill_effect = effect_msg.content
        except asyncio.TimeoutError:
            await ctx.send("Temps écoulé. Création annulée.")
            return

        # Demander la catégorie
        category_embed = discord.Embed(
            title="Catégories de Compétences",
            description="Choisissez une catégorie (1-4):",
            color=0x0099ff
        )
        category_embed.add_field(name="1️⃣ Attaque", 
                               value="Dégâts x1,5, coût 10%, cooldown 1 tour", inline=False)
        category_embed.add_field(name="2️⃣ Bonus", 
                               value="Prochaine attaque +30%, coût 15%, cooldown 2 tours", inline=False)
        category_embed.add_field(name="3️⃣ Malus", 
                               value="Prochaine attaque adverse -30%, coût 15%, cooldown 2 tours", inline=False)
        category_embed.add_field(name="4️⃣ Restreinte", 
                               value="Fait sauter un tour, dégâts x0.8, coût 20%, cooldown 3 tours", inline=False)

        await ctx.send(embed=category_embed)

        try:
            category_msg = await bot.wait_for('message',
                                            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                            timeout=60.0)
            category_choice = category_msg.content.strip()

            category_map = {
                '1': SkillCategory.ATTAQUE,
                '2': SkillCategory.BONUS,
                '3': SkillCategory.MALUS,
                '4': SkillCategory.RESTREINTE
            }

            if category_choice not in category_map:
                await ctx.send("Choix invalide. Création annulée.")
                return

            skill_category = category_map[category_choice]

        except asyncio.TimeoutError:
            await ctx.send("Temps écoulé. Création annulée.")
            return

        # Créer la compétence
        skill = Skill(name=skill_name, effect=skill_effect, category=skill_category)
        character.skills.append(skill)

        await ctx.send(f"✅ Compétence **{skill_name}** créée!")

    # Sauvegarder le personnage
    char_id = db.save_character(character)
    if char_id:
        await ctx.send(f"🎉 Personnage **{nom_complet}** créé avec succès!")
    else:
        await ctx.send("❌ Erreur lors de la création du personnage.")

@bot.command(name='stats', aliases=['statistiques'])
async def show_stats(ctx, *, nom_personnage: str):
    """Afficher les statistiques d'un personnage"""

    character = db.get_character(nom_personnage, ctx.author.id)
    if not character:
        await ctx.send(f"Vous n'avez pas de personnage nommé **{nom_personnage}**.")
        return

    embed = discord.Embed(
        title=f"📊 Statistiques de {character.name}",
        color=0x0099ff
    )

    embed.add_field(name="❤️ Points de Vie", value=f"{character.hp}/{character.max_hp}", inline=True)
    embed.add_field(name="⚡ Jauge de Pouvoir", value=f"{character.power_gauge:.1f}%", inline=True)
    embed.add_field(name="🎯 Talent", value=character.talent.value, inline=True)
    embed.add_field(name="📈 Niveau", value=character.level, inline=True)
    embed.add_field(name="✨ Expérience", value=f"{character.experience}/{character.get_level_threshold()}", inline=True)
    embed.add_field(name="🔮 Compétences", value=str(len(character.skills)), inline=True)

    # Afficher les compétences
    if character.skills:
        skills_text = ""
        for skill in character.skills:
            skills_text += f"**{skill.name}** ({skill.category.value})\n{skill.effect}\n\n"

        if len(skills_text) > 1024:
            skills_text = skills_text[:1021] + "..."

        embed.add_field(name="🎪 Liste des Compétences", value=skills_text, inline=False)

    await ctx.send(embed=embed)

@bot.command(name='mes_personnages', aliases=['mp', 'liste'])
async def my_characters(ctx):
    """Lister tous vos personnages"""

    characters = db.get_all_characters(ctx.author.id)
    if not characters:
        await ctx.send("Vous n'avez aucun personnage. Utilisez `!creer_personnage <nom>` pour en créer un!")
        return

    embed = discord.Embed(
        title=f"👥 Personnages de {ctx.author.display_name}",
        color=0x9932cc
    )

    for character in characters:
        embed.add_field(
            name=f"{character.name}",
            value=f"Niveau {character.level} | {character.talent.value}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='admin_modifier', aliases=['am'])
@commands.has_permissions(administrator=True)
async def admin_modify(ctx, nom_personnage: str, attribut: str, *, nouvelle_valeur: str):
    """Commande administrateur pour modifier n'importe quel personnage"""

    character = db.get_character_by_name_any_owner(nom_personnage)
    if not character:
        await ctx.send(f"Aucun personnage trouvé avec le nom **{nom_personnage}**.")
        return

    # Mapper les attributs
    attributs_valides = {
        'hp': 'hp',
        'pv': 'hp',
        'max_hp': 'max_hp',
        'pv_max': 'max_hp',
        'power_gauge': 'power_gauge',
        'jauge_pouvoir': 'power_gauge',
        'niveau': 'level',
        'level': 'level',
        'experience': 'experience',
        'exp': 'experience',
        'talent': 'talent'
    }

    attribut = attribut.lower()
    if attribut not in attributs_valides:
        await ctx.send(f"Attribut **{attribut}** non reconnu. Attributs valides: {', '.join(attributs_valides.keys())}")
        return

    attr_name = attributs_valides[attribut]

    try:
        if attr_name == 'talent':
            # Conversion du talent
            talent_map = {talent.value.lower(): talent for talent in Talent}
            talent_key = nouvelle_valeur.lower()
            if talent_key not in talent_map:
                await ctx.send(f"Talent invalide. Talents disponibles: {', '.join([t.value for t in Talent])}")
                return
            setattr(character, attr_name, talent_map[talent_key])
        elif attr_name in ['hp', 'max_hp', 'level', 'experience']:
            setattr(character, attr_name, int(nouvelle_valeur))
        elif attr_name == 'power_gauge':
            setattr(character, attr_name, float(nouvelle_valeur))

        # Sauvegarder les modifications
        db.update_character(character)

        await ctx.send(f"✅ **{nom_personnage}** - {attribut} modifié à: **{nouvelle_valeur}**")

    except ValueError:
        await ctx.send("❌ Valeur invalide pour cet attribut.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors de la modification: {str(e)}")

@bot.command(name='ajouter_competence', aliases=['ac'])
async def add_skill(ctx, *, nom_personnage: str):
    """Ajouter une compétence à un personnage (tous les 10 niveaux)"""

    character = db.get_character(nom_personnage, ctx.author.id)
    if not character:
        await ctx.send(f"Vous n'avez pas de personnage nommé **{nom_personnage}**.")
        return

    # Vérifier si le personnage peut apprendre une nouvelle compétence
    expected_skills = 2 + ((character.level - 1) // 10)
    if len(character.skills) >= expected_skills:
        await ctx.send(f"**{nom_personnage}** ne peut pas apprendre de nouvelle compétence pour le moment. "
                      f"(Niveau {character.level}, compétences actuelles: {len(character.skills)}/{expected_skills})")
        return

    await ctx.send(f"**{nom_personnage}** peut apprendre une nouvelle compétence!")

    # Processus de création de compétence (similaire à la création de personnage)
    await ctx.send("Entrez le nom de la compétence:")
    try:
        name_msg = await bot.wait_for('message', 
                                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                    timeout=60.0)
        skill_name = name_msg.content
    except asyncio.TimeoutError:
        await ctx.send("Temps écoulé. Ajout annulé.")
        return

    await ctx.send("Entrez l'effet de la compétence:")
    try:
        effect_msg = await bot.wait_for('message',
                                      check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                      timeout=60.0)
        skill_effect = effect_msg.content
    except asyncio.TimeoutError:
        await ctx.send("Temps écoulé. Ajout annulé.")
        return

    # Sélection de catégorie
    category_embed = discord.Embed(
        title="Catégories de Compétences",
        description="Choisissez une catégorie (1-4):",
        color=0x0099ff
    )
    category_embed.add_field(name="1️⃣ Attaque", 
                           value="Dégâts x1,5, coût 10%, cooldown 1 tour", inline=False)
    category_embed.add_field(name="2️⃣ Bonus", 
                           value="Prochaine attaque +30%, coût 15%, cooldown 2 tours", inline=False)
    category_embed.add_field(name="3️⃣ Malus", 
                           value="Prochaine attaque adverse -30%, coût 15%, cooldown 2 tours", inline=False)
    category_embed.add_field(name="4️⃣ Restreinte", 
                           value="Fait sauter un tour, dégâts x0.8, coût 20%, cooldown 3 tours", inline=False)

    await ctx.send(embed=category_embed)

    try:
        category_msg = await bot.wait_for('message',
                                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                        timeout=60.0)
        category_choice = category_msg.content.strip()

        category_map = {
            '1': SkillCategory.ATTAQUE,
            '2': SkillCategory.BONUS,
            '3': SkillCategory.MALUS,
            '4': SkillCategory.RESTREINTE
        }

        if category_choice not in category_map:
            await ctx.send("Choix invalide. Ajout annulé.")
            return

        skill_category = category_map[category_choice]

    except asyncio.TimeoutError:
        await ctx.send("Temps écoulé. Ajout annulé.")
        return

    # Créer et ajouter la compétence
    skill = Skill(name=skill_name, effect=skill_effect, category=skill_category)
    character.skills.append(skill)

    # Sauvegarder
    db.update_character(character)

    await ctx.send(f"✅ Compétence **{skill_name}** ajoutée à **{nom_personnage}**!")

# ========== COMMANDES DE COMBAT ==========

@bot.command(name='defier', aliases=['combat', 'duel'])
async def challenge_player(ctx, opponent: discord.Member):
    """Défier un autre joueur en combat"""

    if opponent == ctx.author:
        await ctx.send("Vous ne pouvez pas vous défier vous-même!")
        return

    if opponent.bot:
        await ctx.send("Vous ne pouvez pas défier un bot!")
        return

    # Vérifier si les joueurs ont des personnages
    player1_chars = db.get_all_characters(ctx.author.id)
    player2_chars = db.get_all_characters(opponent.id)

    if not player1_chars:
        await ctx.send("Vous n'avez aucun personnage! Créez-en un avec `!creer_personnage`.")
        return

    if not player2_chars:
        await ctx.send(f"{opponent.display_name} n'a aucun personnage!")
        return

    # Créer une session de combat
    session = CombatSession(ctx.author.id, opponent.id, ctx.channel.id)
    combat_system.active_combats[ctx.channel.id] = session

    challenge_embed = discord.Embed(
        title="⚔️ Défi de Combat!",
        description=f"{ctx.author.mention} défie {opponent.mention} en duel!",
        color=0xff4500
    )
    challenge_embed.add_field(
        name="Instructions",
        value="Les deux joueurs doivent choisir un personnage avec `!choisir_personnage <nom>`",
        inline=False
    )

    await ctx.send(embed=challenge_embed)

@bot.command(name='choisir_personnage', aliases=['choisir'])
async def choose_character(ctx, *, nom_personnage: str):
    """Choisir un personnage pour le combat"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.send("Aucun combat en cours dans ce canal!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if ctx.author.id not in [session.player1_id, session.player2_id]:
        await ctx.send("Vous ne participez pas à ce combat!")
        return

    # Récupérer le personnage
    character = db.get_character(nom_personnage, ctx.author.id)
    if not character:
        await ctx.send(f"Vous n'avez pas de personnage nommé **{nom_personnage}**.")
        return

    # Réinitialiser les états de combat
    character.defending = False
    character.defense_cooldown = 0
    character.bonus_next_attack = 1.0
    character.malus_next_received = 1.0
    character.bloodlust_turns = 0
    character.weakened_turns = 0
    character.skip_next_turn = False
    character.was_in_bloodlust = False
    character.hp = character.max_hp
    character.power_gauge = 100.0

    # Réinitialiser les cooldowns des compétences
    for skill in character.skills:
        skill.cooldown = 0

    # Assigner le personnage
    if ctx.author.id == session.player1_id:
        session.player1_character = character
    else:
        session.player2_character = character

    await ctx.send(f"✅ **{nom_personnage}** sélectionné pour le combat!")

    # Vérifier si les deux joueurs ont choisi
    if session.player1_character and session.player2_character:
        await start_objective_selection(ctx, session)

async def start_objective_selection(ctx, session):
    """Commencer la sélection des objectifs de victoire"""

    objectives_embed = discord.Embed(
        title="🎯 Choix des Objectifs de Victoire",
        description="Chaque joueur doit choisir son objectif avec `!objectif <numéro>`",
        color=0x00ff7f
    )
    objectives_embed.add_field(name="1️⃣ K.O.", value="Faire tomber l'adversaire KO (PV à 0)", inline=False)
    objectives_embed.add_field(name="2️⃣ Vider Pouvoir", value="Forcer l'adversaire à vider sa jauge de pouvoir", inline=False)
    objectives_embed.add_field(name="3️⃣ Bloodlust", value="Forcer l'adversaire à consommer son état de bloodlust", inline=False)

    await ctx.send(embed=objectives_embed)

@bot.command(name='objectif')
async def choose_objective(ctx, choix: str):
    """Choisir l'objectif de victoire"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.send("Aucun combat en cours dans ce canal!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if ctx.author.id not in [session.player1_id, session.player2_id]:
        await ctx.send("Vous ne participez pas à ce combat!")
        return

    objective_map = {
        '1': ObjectifVictoire.KO,
        '2': ObjectifVictoire.VIDER_POUVOIR,
        '3': ObjectifVictoire.CONSOMMER_BLOODLUST
    }

    if choix not in objective_map:
        await ctx.send("Choix invalide! Utilisez 1, 2 ou 3.")
        return

    objective = objective_map[choix]

    # Assigner l'objectif
    if ctx.author.id == session.player1_id:
        session.player1_objective = objective
    else:
        session.player2_objective = objective

    await ctx.send(f"✅ Objectif sélectionné: **{objective.value}**")

    # Vérifier si les deux joueurs ont choisi
    if session.both_players_ready():
        await start_rock_paper_scissors(ctx, session)

async def start_rock_paper_scissors(ctx, session):
    """Commencer le pierre-feuille-ciseaux pour déterminer l'ordre"""

    rps_embed = discord.Embed(
        title="✂️ Pierre-Feuille-Ciseaux",
        description="Utilisez `!pfc <choix>` pour jouer\n(pierre, feuille, ciseaux)",
        color=0xffff00
    )

    await ctx.send(embed=rps_embed)

@bot.command(name='pfc', aliases=['rps'])
async def rock_paper_scissors(ctx, choix: str):
    """Jouer pierre-feuille-ciseaux"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.send("Aucun combat en cours dans ce canal!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if ctx.author.id not in [session.player1_id, session.player2_id]:
        return

    valid_choices = ['pierre', 'feuille', 'ciseaux', 'rock', 'paper', 'scissors']
    choix = choix.lower()

    if choix not in valid_choices:
        await ctx.send("Choix invalide! Utilisez: pierre, feuille, ou ciseaux")
        return

    # Normaliser le choix
    choice_map = {
        'pierre': 'pierre', 'rock': 'pierre',
        'feuille': 'feuille', 'paper': 'feuille', 
        'ciseaux': 'ciseaux', 'scissors': 'ciseaux'
    }
    normalized_choice = choice_map[choix]

    session.rps_results[ctx.author.id] = normalized_choice
    await ctx.send("✅ Choix enregistré!")

    # Vérifier si les deux joueurs ont joué
    if len(session.rps_results) == 2:
        await resolve_rps(ctx, session)

async def resolve_rps(ctx, session):
    """Résoudre le pierre-feuille-ciseaux"""

    player1_choice = session.rps_results[session.player1_id]
    player2_choice = session.rps_results[session.player2_id]

    player1 = bot.get_user(session.player1_id)
    player2 = bot.get_user(session.player2_id)

    # Déterminer le gagnant
    win_conditions = {
        ('pierre', 'ciseaux'): session.player1_id,
        ('feuille', 'pierre'): session.player1_id,
        ('ciseaux', 'feuille'): session.player1_id,
        ('ciseaux', 'pierre'): session.player2_id,
        ('pierre', 'feuille'): session.player2_id,
        ('feuille', 'ciseaux'): session.player2_id
    }

    result_embed = discord.Embed(title="✂️ Résultat du Pierre-Feuille-Ciseaux", color=0x00ff00)
    result_embed.add_field(name=player1.display_name, value=player1_choice.capitalize(), inline=True)
    result_embed.add_field(name="VS", value="⚔️", inline=True)
    result_embed.add_field(name=player2.display_name, value=player2_choice.capitalize(), inline=True)

    if (player1_choice, player2_choice) in win_conditions:
        winner_id = win_conditions[(player1_choice, player2_choice)]
        session.current_turn = winner_id
        winner = bot.get_user(winner_id)
        result_embed.add_field(name="🏆 Gagnant", value=f"{winner.display_name} commence!", inline=False)
    else:
        # Égalité
        result_embed.add_field(name="🤝 Égalité", value="Rejouez!", inline=False)
        session.rps_results.clear()
        await ctx.send(embed=result_embed)
        return

    await ctx.send(embed=result_embed)

    # Commencer le combat
    session.combat_started = True
    session.turn_count = 1
    await show_combat_status(ctx, session)

async def show_combat_status(ctx, session):
    """Afficher le statut actuel du combat"""

    char1 = session.player1_character
    char2 = session.player2_character
    player1 = bot.get_user(session.player1_id)
    player2 = bot.get_user(session.player2_id)
    current_player = bot.get_user(session.current_turn)

    embed = discord.Embed(
        title=f"⚔️ Combat - Tour {session.turn_count}",
        description=f"C'est au tour de **{current_player.display_name}**!",
        color=0xff6b6b
    )

    # Statut du personnage 1
    p1_status = f"❤️ {char1.hp}/{char1.max_hp} PV\n⚡ {char1.power_gauge:.1f}%"
    if char1.bloodlust_turns > 0:
        p1_status += f"\n🔥 Bloodlust ({char1.bloodlust_turns} tours)"
    if char1.weakened_turns > 0:
        p1_status += f"\n😵 Affaibli ({char1.weakened_turns} tours)"
    if char1.defending:
        p1_status += "\n🛡️ En défense"
    if char1.defense_cooldown > 0:
        p1_status += f"\n⏳ Défense en recharge ({char1.defense_cooldown})"

    embed.add_field(
        name=f"👤 {player1.display_name} - {char1.name}",
        value=p1_status,
        inline=True
    )

    embed.add_field(name="🆚", value="⚔️", inline=True)

    # Statut du personnage 2
    p2_status = f"❤️ {char2.hp}/{char2.max_hp} PV\n⚡ {char2.power_gauge:.1f}%"
    if char2.bloodlust_turns > 0:
        p2_status += f"\n🔥 Bloodlust ({char2.bloodlust_turns} tours)"
    if char2.weakened_turns > 0:
        p2_status += f"\n😵 Affaibli ({char2.weakened_turns} tours)"
    if char2.defending:
        p2_status += "\n🛡️ En défense"
    if char2.defense_cooldown > 0:
        p2_status += f"\n⏳ Défense en recharge ({char2.defense_cooldown})"

    embed.add_field(
        name=f"👤 {player2.display_name} - {char2.name}",
        value=p2_status,
        inline=True
    )

    # Actions disponibles
    actions_text = "Utilisez:\n`!attaque` - Attaque basique\n`!competence <nom>` - Utiliser une compétence\n`!defense` - Se défendre"
    embed.add_field(name="🎮 Actions", value=actions_text, inline=False)

    await ctx.send(embed=embed)

@bot.command(name='attaque', aliases=['attaquer'])
async def basic_attack(ctx):
    """Effectuer une attaque basique"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.send("Aucun combat en cours!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if not session.combat_started:
        await ctx.send("Le combat n'a pas encore commencé!")
        return

    if ctx.author.id != session.current_turn:
        await ctx.send("Ce n'est pas votre tour!")
        return

    attacker = session.get_character(ctx.author.id)
    defender = session.get_opponent_character(ctx.author.id)

    # Vérifier si le personnage doit sauter son tour
    if attacker.skip_next_turn:
        attacker.skip_next_turn = False
        await ctx.send(f"**{attacker.name}** doit sauter ce tour à cause d'une compétence restreinte!")
        await end_turn(ctx, session)
        return

    # Vérifier l'état de bloodlust (30% de chance d'action aléatoire)
    if attacker.bloodlust_turns > 0 and random.random() < 0.3:
        actions = [CombatAction.COMPETENCE, CombatAction.DEFENSE]
        random_action = random.choice(actions)
        await ctx.send(f"🔥 **{attacker.name}** en bloodlust agit de manière imprévisible!")

        if random_action == CombatAction.DEFENSE:
            await defense_action(ctx, attacker, defender, session)
        else:
            # Choisir une compétence aléatoire utilisable
            available_skills = [s for s in attacker.skills if s.cooldown == 0 and 
                             attacker.power_gauge >= s.get_power_cost()]
            if available_skills:
                random_skill = random.choice(available_skills)
                await skill_action(ctx, attacker, defender, session, random_skill)
            else:
                # Pas de compétence disponible, attaque basique
                await attack_action(ctx, attacker, defender, session)
    else:
        await attack_action(ctx, attacker, defender, session)

async def attack_action(ctx, attacker: Character, defender: Character, session):
    """Exécuter une attaque basique"""

    damage = combat_system.calculate_damage(attacker, defender)

    # Récupération de PV en bloodlust (30% de chance)
    heal_amount = 0
    if attacker.bloodlust_turns > 0 and random.random() < 0.3:
        heal_amount = int(damage * 0.25)
        attacker.hp = min(attacker.max_hp, attacker.hp + heal_amount)

    # Appliquer les dégâts
    defender.hp = max(0, defender.hp - damage)

    # Message d'attaque
    attack_msg = f"⚔️ **{attacker.name}** attaque **{defender.name}** pour **{damage}** dégâts!"
    if heal_amount > 0:
        attack_msg += f"\n💖 **{attacker.name}** récupère **{heal_amount}** PV grâce au bloodlust!"

    await ctx.send(attack_msg)

    # Vérifier les conditions de victoire
    winner_id = combat_system.check_victory_conditions(session)
    if winner_id:
        await end_combat(ctx, session, winner_id)
        return

    await end_turn(ctx, session)

@bot.command(name='competence', aliases=['skill'])
async def use_skill_command(ctx, *, nom_competence: str):
    """Utiliser une compétence"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.send("Aucun combat en cours!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if not session.combat_started:
        await ctx.send("Le combat n'a pas encore commencé!")
        return

    if ctx.author.id != session.current_turn:
        await ctx.send("Ce n'est pas votre tour!")
        return

    attacker = session.get_character(ctx.author.id)
    defender = session.get_opponent_character(ctx.author.id)

    # Vérifier si le personnage doit sauter son tour
    if attacker.skip_next_turn:
        attacker.skip_next_turn = False
        await ctx.send(f"**{attacker.name}** doit sauter ce tour à cause d'une compétence restreinte!")
        await end_turn(ctx, session)
        return

    # Trouver la compétence
    skill = None
    for s in attacker.skills:
        if s.name.lower() == nom_competence.lower():
            skill = s
            break

    if not skill:
        await ctx.send(f"Compétence **{nom_competence}** non trouvée!")
        return

    # Vérifier si la compétence peut être utilisée
    if skill.cooldown > 0:
        await ctx.send(f"**{skill.name}** est en cooldown ({skill.cooldown} tours restants)!")
        return

    if attacker.power_gauge < skill.get_power_cost():
        await ctx.send(f"Jauge de pouvoir insuffisante! (**{skill.get_power_cost()}%** requis)")
        return

    await skill_action(ctx, attacker, defender, session, skill)

async def skill_action(ctx, attacker: Character, defender: Character, session, skill: Skill):
    """Exécuter une action de compétence"""

    # Utiliser la compétence
    combat_system.use_skill(attacker, skill, defender)

    skill_msg = f"✨ **{attacker.name}** utilise **{skill.name}**!"

    damage = 0
    heal_amount = 0

    # Calculer et appliquer les dégâts si c'est une compétence d'attaque ou restreinte
    if skill.category in [SkillCategory.ATTAQUE, SkillCategory.RESTREINTE]:
        damage = combat_system.calculate_damage(attacker, defender, True, skill.category)

        # Récupération de PV en bloodlust (30% de chance)
        if attacker.bloodlust_turns > 0 and random.random() < 0.3:
            heal_amount = int(damage * 0.25)
            attacker.hp = min(attacker.max_hp, attacker.hp + heal_amount)

        # Appliquer les dégâts
        defender.hp = max(0, defender.hp - damage)
        skill_msg += f"\n💥 **{damage}** dégâts infligés!"

    # Messages spéciaux selon la catégorie
    if skill.category == SkillCategory.BONUS:
        skill_msg += "\n🔥 Prochaine attaque renforcée!"
    elif skill.category == SkillCategory.MALUS:
        skill_msg += "\n🛡️ Prochaine attaque adverse affaiblie!"
    elif skill.category == SkillCategory.RESTREINTE:
        skill_msg += "\n⏸️ L'adversaire sautera son prochain tour!"

    if heal_amount > 0:
        skill_msg += f"\n💖 **{attacker.name}** récupère **{heal_amount}** PV!"

    await ctx.send(skill_msg)

    # Vérifier les conditions de victoire
    winner_id = combat_system.check_victory_conditions(session)
    if winner_id:
        await end_combat(ctx, session, winner_id)
        return

    await end_turn(ctx, session)

@bot.command(name='defense', aliases=['defendre'])
async def defend_command(ctx):
    """Se défendre"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.send("Aucun combat en cours!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if not session.combat_started:
        await ctx.send("Le combat n'a pas encore commencé!")
        return

    if ctx.author.id != session.current_turn:
        await ctx.send("Ce n'est pas votre tour!")
        return

    attacker = session.get_character(ctx.author.id)
    defender = session.get_opponent_character(ctx.author.id)

    await defense_action(ctx, attacker, defender, session)

async def defense_action(ctx, character: Character, opponent: Character, session):
    """Exécuter une action de défense"""

    # Vérifier si le personnage doit sauter son tour
    if character.skip_next_turn:
        character.skip_next_turn = False
        await ctx.send(f"**{character.name}** doit sauter ce tour à cause d'une compétence restreinte!")
        await end_turn(ctx, session)
        return

    # Vérifier si la défense est en cooldown
    if character.defense_cooldown > 0:
        await ctx.send(f"🛡️ Défense en cooldown ({character.defense_cooldown} tours restants)!")
        return

    # Activer la défense
    character.defending = True
    await ctx.send(f"🛡️ **{character.name}** se met en position de défense!")

    await end_turn(ctx, session)

@bot.command(name='bloodlust', aliases=['bl'])
async def enter_bloodlust(ctx):
    """Entrer en état de bloodlust quand la jauge de pouvoir est à 0"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.send("Aucun combat en cours!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if ctx.author.id not in [session.player1_id, session.player2_id]:
        await ctx.send("Vous ne participez pas à ce combat!")
        return

    character = session.get_character(ctx.author.id)

    # Vérifier si le personnage peut entrer en bloodlust
    if character.power_gauge > 0:
        await ctx.send("Vous ne pouvez entrer en bloodlust qu'avec une jauge de pouvoir vide!")
        return

    if character.bloodlust_turns > 0:
        await ctx.send("Vous êtes déjà en état de bloodlust!")
        return

    # Vérifier si c'est la condition de victoire adverse
    opponent_id = session.get_opponent_id(ctx.author.id)
    opponent_objective = session.player1_objective if opponent_id == session.player1_id else session.player2_objective

    if opponent_objective == ObjectifVictoire.VIDER_POUVOIR:
        await ctx.send("❌ Vous ne pouvez pas entrer en bloodlust car c'est la condition de victoire de votre adversaire!")
        await end_combat(ctx, session, opponent_id)
        return

    # Activer le bloodlust
    character.bloodlust_turns = 8
    character.power_gauge = 100.0
    character.was_in_bloodlust = True

    bloodlust_embed = discord.Embed(
        title="🔥 BLOODLUST ACTIVÉ!",
        description=f"**{character.name}** entre dans un état de rage incontrôlable!",
        color=0xff0000
    )
    bloodlust_embed.add_field(name="Effets", 
                             value="• Dégâts x2\n• Dégâts reçus x2\n• 30% de chances d'actions imprévisibles\n• 30% de chances de récupération de PV", 
                             inline=False)
    bloodlust_embed.add_field(name="Durée", value="8 tours + 2 tours d'affaiblissement", inline=False)

    await ctx.send(embed=bloodlust_embed)

    # Continuer le combat
    await show_combat_status(ctx, session)

async def end_turn(ctx, session):
    """Terminer le tour actuel"""

    current_char = session.get_character(session.current_turn)

    # Traiter les effets de fin de tour
    combat_system.process_turn_end(current_char)

    # Passer au joueur suivant
    session.current_turn = session.get_opponent_id(session.current_turn)
    session.turn_count += 1

    # Afficher le statut du combat
    await show_combat_status(ctx, session)

async def end_combat(ctx, session, winner_id: int):
    """Terminer le combat"""

    winner = bot.get_user(winner_id)
    loser_id = session.get_opponent_id(winner_id)
    loser = bot.get_user(loser_id)

    winner_char = session.get_character(winner_id)
    loser_char = session.get_character(loser_id)

    # Calculer l'expérience (simplifié pour l'exemple)
    winner_exp = combat_system.calculate_experience(
        winner_char, 1000 - loser_char.hp, True, 
        winner_char.hp, winner_char.power_gauge
    )
    loser_exp = combat_system.calculate_experience(
        loser_char, 1000 - winner_char.hp, False,
        loser_char.hp, loser_char.power_gauge
    )

    # Appliquer l'expérience
    winner_char.experience += winner_exp
    loser_char.experience += loser_exp

    # Vérifier les montées de niveau
    winner_leveled = winner_char.can_level_up()
    loser_leveled = loser_char.can_level_up()

    if winner_leveled:
        winner_char.level_up()
    if loser_leveled:
        loser_char.level_up()

    # Réinitialiser les statistiques
    winner_char.hp = winner_char.max_hp
    winner_char.power_gauge = 100.0
    loser_char.hp = loser_char.max_hp
    loser_char.power_gauge = 100.0

    # Sauvegarder les personnages
    db.update_character(winner_char)
    db.update_character(loser_char)

    # Message de fin
    end_embed = discord.Embed(
        title="🏆 Fin du Combat!",
        description=f"**{winner.display_name}** remporte la victoire!",
        color=0xffd700
    )

    end_embed.add_field(
        name=f"🎉 {winner.display_name}",
        value=f"**{winner_exp}** XP gagnés" + (f"\n📈 **NIVEAU UP!** Niveau {winner_char.level}" if winner_leveled else ""),
        inline=True
    )

    end_embed.add_field(
        name=f"😔 {loser.display_name}",
        value=f"**{loser_exp}** XP gagnés" + (f"\n📈 **NIVEAU UP!** Niveau {loser_char.level}" if loser_leveled else ""),
        inline=True
    )

    await ctx.send(embed=end_embed)

    # Nettoyer la session de combat
    del combat_system.active_combats[ctx.channel.id]

@bot.command(name='forfait', aliases=['abandon'])
async def forfeit_combat(ctx):
    """Abandonner le combat en cours"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.send("Aucun combat en cours!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if ctx.author.id not in [session.player1_id, session.player2_id]:
        await ctx.send("Vous ne participez pas à ce combat!")
        return

    # Déterminer le gagnant (l'adversaire)
    winner_id = session.get_opponent_id(ctx.author.id)

    await ctx.send(f"🏳️ **{ctx.author.display_name}** abandonne le combat!")
    await end_combat(ctx, session, winner_id)

@bot.command(name='mes_competences', aliases=['competences'])
async def show_skills_in_combat(ctx):
    """Afficher vos compétences disponibles pendant un combat"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.send("Utilisez cette commande pendant un combat!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if ctx.author.id not in [session.player1_id, session.player2_id]:
        return

    character = session.get_character(ctx.author.id)

    if not character.skills:
        await ctx.send("Vous n'avez aucune compétence!")
        return

    embed = discord.Embed(
        title=f"🎪 Compétences de {character.name}",
        color=0x9932cc
    )

    for skill in character.skills:
        status = ""
        if skill.cooldown > 0:
            status += f"⏳ Cooldown: {skill.cooldown} tours\n"

        power_cost = skill.get_power_cost()
        can_use = character.power_gauge >= power_cost and skill.cooldown == 0

        status += f"⚡ Coût: {power_cost}%\n"
        status += f"🔄 Cooldown max: {skill.get_cooldown_duration()} tours\n"
        status += f"{'✅ Disponible' if can_use else '❌ Indisponible'}"

        embed.add_field(
            name=f"{skill.name} ({skill.category.value})",
            value=f"{skill.effect}\n\n{status}",
            inline=False
        )

    await ctx.send(embed=embed)

# ========== COMMANDES UTILITAIRES ==========

@bot.command(name='aide_combat', aliases=['help_combat'])
async def combat_help(ctx):
    """Guide des commandes de combat"""

    embed = discord.Embed(
        title="⚔️ Guide du Système de Combat",
        color=0x0099ff
    )

    embed.add_field(
        name="🎯 Démarrer un Combat",
        value="`!defier @joueur` - Défier un joueur\n`!choisir_personnage <nom>` - Sélectionner son personnage\n`!objectif <1-3>` - Choisir l'objectif de victoire\n`!pfc <pierre/feuille/ciseaux>` - Déterminer l'ordre",
        inline=False
    )

    embed.add_field(
        name="🎮 Actions de Combat",
        value="`!attaque` - Attaque basique (100 dégâts de base)\n`!competence <nom>` - Utiliser une compétence\n`!defense` - Se défendre (réduit les dégâts de 50%)\n`!mes_competences` - Voir ses compétences",
        inline=False
    )

    embed.add_field(
        name="🔥 États Spéciaux",
        value="`!bloodlust` - Entrer en bloodlust (jauge vide uniquement)\n`!forfait` - Abandonner le combat",
        inline=False
    )

    embed.add_field(
        name="🎯 Objectifs de Victoire",
        value="1️⃣ **K.O.** - Réduire les PV adverses à 0\n2️⃣ **Vider Pouvoir** - Vider la jauge de pouvoir adverse\n3️⃣ **Bloodlust** - Forcer l'adversaire à consommer son bloodlust",
        inline=False
    )

    embed.add_field(
        name="🎪 Catégories de Compétences",
        value="🗡️ **Attaque** - Dégâts x1,5, coût 10%, cooldown 1\n💪 **Bonus** - Prochaine attaque +30%, coût 15%, cooldown 2\n🛡️ **Malus** - Prochaine attaque adverse -30%, coût 15%, cooldown 2\n⏸️ **Restreinte** - Fait sauter un tour, dégâts x0.8, coût 20%, cooldown 3",
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command(name='talents', aliases=['talent_info'])
async def talent_info(ctx):
    """Informations sur les talents et leurs interactions"""

    embed = discord.Embed(
        title="🎭 Système de Talents",
        description="Les talents donnent des avantages/désavantages en combat (+10% ou -10% de dégâts)",
        color=0xffa500
    )

    embed.add_field(
        name="⚡ Yeux de Dieu",
        value="**Avantage contre:** Dieu de la Vitesse\n**Désavantage contre:** Overpowered",
        inline=True
    )

    embed.add_field(
        name="💨 Dieu de la Vitesse", 
        value="**Avantage contre:** Inégalé\n**Désavantage contre:** Yeux de Dieu",
        inline=True
    )

    embed.add_field(
        name="⭐ Inégalé",
        value="**Avantage contre:** Forteresse\n**Désavantage contre:** Dieu de la Vitesse", 
        inline=True
    )

    embed.add_field(
        name="🛡️ Forteresse",
        value="**Avantage contre:** Overpowered\n**Désavantage contre:** Inégalé",
        inline=True
    )

    embed.add_field(
        name="💥 Overpowered", 
        value="**Avantage contre:** Yeux de Dieu\n**Désavantage contre:** Forteresse",
        inline=True
    )

    embed.add_field(
        name="🔄 Cycle des Avantages",
        value="Yeux de Dieu → Dieu de la Vitesse → Inégalé → Forteresse → Overpowered → Yeux de Dieu",
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command(name='classement', aliases=['leaderboard', 'top'])
async def leaderboard(ctx, critere: str = "niveau"):
    """Afficher le classement des personnages"""

    # Récupérer tous les personnages de tous les joueurs
    cursor = db.conn.cursor()

    if critere.lower() in ['niveau', 'level', 'lvl']:
        cursor.execute("""
            SELECT name, owner_id, level, talent FROM characters 
            ORDER BY level DESC, experience DESC LIMIT 10
        """)
        title = "🏆 Classement par Niveau"
    elif critere.lower() in ['experience', 'exp', 'xp']:
        cursor.execute("""
            SELECT name, owner_id, experience, talent FROM characters 
            ORDER BY experience DESC LIMIT 10
        """)
        title = "✨ Classement par Expérience"
    else:
        await ctx.send("Critères disponibles: `niveau` ou `experience`")
        return

    results = cursor.fetchall()

    if not results:
        await ctx.send("Aucun personnage trouvé!")
        return

    embed = discord.Embed(title=title, color=0xffd700)

    for i, (name, owner_id, value, talent) in enumerate(results, 1):
        try:
            user = bot.get_user(owner_id)
            user_name = user.display_name if user else "Utilisateur inconnu"
        except:
            user_name = "Utilisateur inconnu"

        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

        embed.add_field(
            name=f"{medal} {name}",
            value=f"**Joueur:** {user_name}\n**{critere.capitalize()}:** {value}\n**Talent:** {talent}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='statistiques_globales', aliases=['stats_globales'])
async def global_stats(ctx):
    """Afficher les statistiques globales du bot"""

    cursor = db.conn.cursor()

    # Compter les personnages
    cursor.execute("SELECT COUNT(*) FROM characters")
    total_characters = cursor.fetchone()[0]

    # Compter les joueurs uniques
    cursor.execute("SELECT COUNT(DISTINCT owner_id) FROM characters")
    total_players = cursor.fetchone()[0]

    # Niveau moyen
    cursor.execute("SELECT AVG(level) FROM characters")
    avg_level = cursor.fetchone()[0] or 0

    # Personnage avec le plus haut niveau
    cursor.execute("SELECT name, level FROM characters ORDER BY level DESC, experience DESC LIMIT 1")
    top_char = cursor.fetchone()

    # Distribution des talents
    cursor.execute("SELECT talent, COUNT(*) FROM characters GROUP BY talent")
    talent_distribution = cursor.fetchall()

    embed = discord.Embed(
        title="📊 Statistiques Globales du Bot",
        color=0x00ff7f
    )

    embed.add_field(name="👥 Joueurs Total", value=str(total_players), inline=True)
    embed.add_field(name="🎭 Personnages Total", value=str(total_characters), inline=True)
    embed.add_field(name="📈 Niveau Moyen", value=f"{avg_level:.1f}", inline=True)

    if top_char:
        embed.add_field(name="🏆 Plus Haut Niveau", value=f"{top_char[0]} (Niv. {top_char[1]})", inline=True)

    if talent_distribution:
        talent_text = "\n".join([f"{talent}: {count}" for talent, count in talent_distribution])
        embed.add_field(name="🎯 Distribution des Talents", value=talent_text, inline=False)

    await ctx.send(embed=embed)

@bot.command(name='supprimer_personnage', aliases=['delete_char'])
async def delete_character(ctx, *, nom_personnage: str):
    """Supprimer un de vos personnages"""

    character = db.get_character(nom_personnage, ctx.author.id)
    if not character:
        await ctx.send(f"Vous n'avez pas de personnage nommé **{nom_personnage}**.")
        return

    # Demander confirmation
    confirm_embed = discord.Embed(
        title="⚠️ Confirmation de Suppression",
        description=f"Êtes-vous sûr de vouloir supprimer **{nom_personnage}** ?\n\n**Cette action est irréversible!**",
        color=0xff4444
    )
    confirm_embed.add_field(name="Pour confirmer", value="Tapez `CONFIRMER` dans les 30 secondes", inline=False)

    await ctx.send(embed=confirm_embed)

    try:
        confirmation = await bot.wait_for('message',
                                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                        timeout=30.0)

        if confirmation.content.upper() == "CONFIRMER":
            db.delete_character(nom_personnage, ctx.author.id)
            await ctx.send(f"✅ **{nom_personnage}** a été supprimé.")
        else:
            await ctx.send("❌ Suppression annulée.")
    except asyncio.TimeoutError:
        await ctx.send("⏰ Temps écoulé. Suppression annulée.")

@bot.command(name='commandes', aliases=['aide'])
async def show_commands(ctx):
    """Afficher toutes les commandes disponibles"""

    embed = discord.Embed(
        title="🤖 Commandes du Bot RPG Discord",
        description="Voici toutes les commandes disponibles:",
        color=0x0099ff
    )

    embed.add_field(
        name="👤 Gestion des Personnages",
        value="`!creer_personnage <nom>` - Créer un personnage\n`!stats <nom>` - Voir les statistiques\n`!mes_personnages` - Lister vos personnages\n`!ajouter_competence <nom>` - Ajouter une compétence\n`!supprimer_personnage <nom>` - Supprimer un personnage",
        inline=False
    )

    embed.add_field(
        name="⚔️ Combat",
        value="`!defier @joueur` - Défier un joueur\n`!choisir_personnage <nom>` - Choisir son personnage\n`!objectif <1-3>` - Choisir l'objectif\n`!pfc <choix>` - Pierre-feuille-ciseaux\n`!attaque` - Attaque basique\n`!competence <nom>` - Utiliser une compétence\n`!defense` - Se défendre\n`!bloodlust` - Entrer en bloodlust\n`!forfait` - Abandonner",
        inline=False
    )

    embed.add_field(
        name="📊 Informations",
        value="`!aide_combat` - Guide du combat\n`!talents` - Infos sur les talents\n`!classement <critère>` - Classement\n`!statistiques_globales` - Stats du bot\n`!mes_competences` - Compétences en combat",
        inline=False
    )

    embed.add_field(
        name="⚙️ Administration",
        value="`!admin_modifier <nom> <attribut> <valeur>` - Modifier un personnage (admin seulement)",
        inline=False
    )

    await ctx.send(embed=embed)

# ========== GESTION DES ERREURS ==========

@admin_modify.error
async def admin_modify_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Vous devez être administrateur pour utiliser cette commande.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Commande non trouvée! Utilisez `!aide` pour voir toutes les commandes.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argument manquant! Utilisez `!aide` pour voir la syntaxe correcte.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Argument invalide! Vérifiez la syntaxe de la commande.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Vous n'avez pas les permissions nécessaires pour cette commande.")
    else:
        print(f"Erreur non gérée: {error}")
        await ctx.send("❌ Une erreur inattendue s'est produite.")

# ========== POINT D'ENTRÉE ==========

if __name__ == "__main__":
    print("🚀 Démarrage du Bot RPG Discord...")
    print("📝 N'oubliez pas de remplacer 'VOTRE_TOKEN_ICI' par votre vrai token Discord!")
    print("🔧 Assurez-vous d'avoir installé discord.py: pip install discord.py")

    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("❌ Erreur de connexion: Token Discord invalide!")
    except Exception as e:
        print(f"❌ Erreur lors du démarrage: {e}")
