
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
bot = discord.Bot(intents=intents)

# Enums et classes de données (identiques)
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
    cooldown: int = 0

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

# Classes pour gérer les combats (identiques)
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
        self.rps_results = {}
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

# Système de base de données (identique)
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('discord_rpg.db')
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

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
            cursor.execute("""
                INSERT INTO characters (name, owner_id, hp, max_hp, power_gauge, talent, level, experience)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (character.name, character.owner_id, character.hp, character.max_hp, 
                  character.power_gauge, character.talent.value, character.level, character.experience))

            character_id = cursor.lastrowid

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

        cursor.execute("""
            UPDATE characters 
            SET hp = ?, max_hp = ?, power_gauge = ?, talent = ?, level = ?, experience = ?
            WHERE name = ? AND owner_id = ?
        """, (character.hp, character.max_hp, character.power_gauge, character.talent.value, 
              character.level, character.experience, character.name, character.owner_id))

        cursor.execute("SELECT id FROM characters WHERE name = ? AND owner_id = ?", 
                      (character.name, character.owner_id))
        char_id = cursor.fetchone()[0]

        cursor.execute("DELETE FROM skills WHERE character_id = ?", (char_id,))

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

        cursor.execute("SELECT id FROM characters WHERE name = ? AND owner_id = ?", 
                      (name, owner_id))
        char_data = cursor.fetchone()
        if char_data:
            char_id = char_data[0]
            cursor.execute("DELETE FROM skills WHERE character_id = ?", (char_id,))
            cursor.execute("DELETE FROM characters WHERE id = ?", (char_id,))
            self.conn.commit()

# Système de combat (identique)
class CombatSystem:
    def __init__(self):
        self.active_combats = {}
        self.pending_combats = {}

    def calculate_damage(self, attacker: Character, defender: Character, 
                        is_skill: bool = False, skill_category: SkillCategory = None) -> int:
        base_damage = 100

        talent_modifier = attacker.get_talent_advantage(defender.talent)

        skill_modifier = 1.0
        if is_skill:
            if skill_category == SkillCategory.ATTAQUE:
                skill_modifier = 1.5
            elif skill_category == SkillCategory.RESTREINTE:
                skill_modifier = 0.8

        bloodlust_modifier = 2.0 if attacker.bloodlust_turns > 0 else 1.0
        weakened_modifier = 0.5 if attacker.weakened_turns > 0 else 1.0
        bonus_modifier = attacker.bonus_next_attack
        defense_modifier = 0.5 if defender.defending else 1.0
        malus_modifier = defender.malus_next_received

        damage = (base_damage * talent_modifier * skill_modifier * 
                 bloodlust_modifier * weakened_modifier * bonus_modifier * 
                 defense_modifier * malus_modifier)

        if defender.bloodlust_turns > 0:
            damage *= 2.0
        elif defender.weakened_turns > 0:
            damage *= 2.0

        return int(damage)

    def use_skill(self, character: Character, skill: Skill, opponent: Character) -> bool:
        if skill.cooldown > 0:
            return False

        if character.power_gauge < skill.get_power_cost():
            return False

        character.power_gauge -= skill.get_power_cost()

        if skill.category == SkillCategory.BONUS:
            character.bonus_next_attack = 1.3
        elif skill.category == SkillCategory.MALUS:
            opponent.malus_next_received = 0.7
        elif skill.category == SkillCategory.RESTREINTE:
            opponent.skip_next_turn = True

        skill.cooldown = skill.get_cooldown_duration()

        return True

    def process_turn_end(self, character: Character):
        for skill in character.skills:
            if skill.cooldown > 0:
                skill.cooldown -= 1

        if character.defense_cooldown > 0:
            character.defense_cooldown -= 1

        character.bonus_next_attack = 1.0
        character.malus_next_received = 1.0
        character.defending = False

        if character.bloodlust_turns > 0:
            character.bloodlust_turns -= 1
            if character.bloodlust_turns == 0:
                character.weakened_turns = 2

        if character.weakened_turns > 0:
            character.weakened_turns -= 1

    def check_victory_conditions(self, session: CombatSession) -> Optional[int]:
        char1 = session.player1_character
        char2 = session.player2_character
        obj1 = session.player1_objective
        obj2 = session.player2_objective

        if char1.hp <= 0:
            if obj2 == ObjectifVictoire.KO:
                return session.player2_id
            return None

        if char2.hp <= 0:
            if obj1 == ObjectifVictoire.KO:
                return session.player1_id
            return None

        if char1.power_gauge <= 0:
            if obj2 == ObjectifVictoire.VIDER_POUVOIR:
                return session.player2_id
            return None

        if char2.power_gauge <= 0:
            if obj1 == ObjectifVictoire.VIDER_POUVOIR:
                return session.player1_id
            return None

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
        base_exp = 0

        if victory:
            base_exp += 2000

        base_exp += damage_dealt
        base_exp += final_hp

        power_multiplier = 1.0 + (final_power / 100.0)

        return int(base_exp * power_multiplier)

# Instances globales
db = Database()
combat_system = CombatSystem()

# ========== COMMANDES SLASH ==========

@bot.event
async def on_ready():
    print(f'{bot.user} est connecté et prêt!')
    print(f'Bot actif sur {len(bot.guilds)} serveur(s)')
    await bot.change_presence(activity=discord.Game(name="RPG Discord | /aide"))

@bot.slash_command(name="creer_personnage", description="Créer un nouveau personnage")
async def create_character(ctx, nom_complet: str):
    """Créer un nouveau personnage"""

    existing_char = db.get_character(nom_complet, ctx.author.id)
    if existing_char:
        await ctx.respond(f"Vous avez déjà un personnage nommé **{nom_complet}**!")
        return

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

    await ctx.respond(embed=embed)

    # Processus de création des compétences
    await ctx.followup.send("Vous pouvez maintenant créer **2 compétences** pour votre personnage.")

    for i in range(2):
        await ctx.followup.send(f"**Compétence {i+1}/2**")

        # Demander le nom de la compétence
        await ctx.followup.send("Entrez le nom de la compétence:")
        try:
            name_msg = await bot.wait_for('message', 
                                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                        timeout=60.0)
            skill_name = name_msg.content
        except asyncio.TimeoutError:
            await ctx.followup.send("Temps écoulé. Création annulée.")
            return

        # Demander l'effet de la compétence
        await ctx.followup.send("Entrez l'effet de la compétence:")
        try:
            effect_msg = await bot.wait_for('message',
                                          check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                          timeout=60.0)
            skill_effect = effect_msg.content
        except asyncio.TimeoutError:
            await ctx.followup.send("Temps écoulé. Création annulée.")
            return

        # Demander la catégorie avec Select Menu
        class CategorySelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label="Attaque", description="Dégâts x1,5, coût 10%, cooldown 1 tour", value="1"),
                    discord.SelectOption(label="Bonus", description="Prochaine attaque +30%, coût 15%, cooldown 2 tours", value="2"),
                    discord.SelectOption(label="Malus", description="Prochaine attaque adverse -30%, coût 15%, cooldown 2 tours", value="3"),
                    discord.SelectOption(label="Restreinte", description="Fait sauter un tour, dégâts x0.8, coût 20%, cooldown 3 tours", value="4")
                ]
                super().__init__(placeholder="Choisissez une catégorie...", options=options)

            async def callback(self, interaction: discord.Interaction):
                category_map = {
                    '1': SkillCategory.ATTAQUE,
                    '2': SkillCategory.BONUS,
                    '3': SkillCategory.MALUS,
                    '4': SkillCategory.RESTREINTE
                }

                skill_category = category_map[self.values[0]]
                skill = Skill(name=skill_name, effect=skill_effect, category=skill_category)
                character.skills.append(skill)

                await interaction.response.send_message(f"✅ Compétence **{skill_name}** créée!")

                if len(character.skills) == 2:
                    char_id = db.save_character(character)
                    if char_id:
                        await ctx.followup.send(f"🎉 Personnage **{nom_complet}** créé avec succès!")
                    else:
                        await ctx.followup.send("❌ Erreur lors de la création du personnage.")

        class CategoryView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.add_item(CategorySelect())

            async def on_timeout(self):
                await ctx.followup.send("Temps écoulé. Création annulée.")

        await ctx.followup.send("Choisissez une catégorie:", view=CategoryView())

@bot.slash_command(name="stats", description="Afficher les statistiques d'un personnage")
async def show_stats(ctx, nom_personnage: str):
    """Afficher les statistiques d'un personnage"""

    character = db.get_character(nom_personnage, ctx.author.id)
    if not character:
        await ctx.respond(f"Vous n'avez pas de personnage nommé **{nom_personnage}**.")
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

    if character.skills:
        skills_text = ""
        for skill in character.skills:
            skills_text += f"**{skill.name}** ({skill.category.value})\n{skill.effect}\n\n"

        if len(skills_text) > 1024:
            skills_text = skills_text[:1021] + "..."

        embed.add_field(name="🎪 Liste des Compétences", value=skills_text, inline=False)

    await ctx.respond(embed=embed)

@bot.slash_command(name="mes_personnages", description="Lister tous vos personnages")
async def my_characters(ctx):
    """Lister tous vos personnages"""

    characters = db.get_all_characters(ctx.author.id)
    if not characters:
        await ctx.respond("Vous n'avez aucun personnage. Utilisez `/creer_personnage` pour en créer un!")
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

    await ctx.respond(embed=embed)

@bot.slash_command(name="defier", description="Défier un autre joueur en combat")
async def challenge_player(ctx, opponent: discord.Member):
    """Défier un autre joueur en combat"""

    if opponent == ctx.author:
        await ctx.respond("Vous ne pouvez pas vous défier vous-même!")
        return

    if opponent.bot:
        await ctx.respond("Vous ne pouvez pas défier un bot!")
        return

    player1_chars = db.get_all_characters(ctx.author.id)
    player2_chars = db.get_all_characters(opponent.id)

    if not player1_chars:
        await ctx.respond("Vous n'avez aucun personnage! Créez-en un avec `/creer_personnage`.")
        return

    if not player2_chars:
        await ctx.respond(f"{opponent.display_name} n'a aucun personnage!")
        return

    session = CombatSession(ctx.author.id, opponent.id, ctx.channel.id)
    combat_system.active_combats[ctx.channel.id] = session

    challenge_embed = discord.Embed(
        title="⚔️ Défi de Combat!",
        description=f"{ctx.author.mention} défie {opponent.mention} en duel!",
        color=0xff4500
    )
    challenge_embed.add_field(
        name="Instructions",
        value="Les deux joueurs doivent choisir un personnage avec `/choisir_personnage`",
        inline=False
    )

    await ctx.respond(embed=challenge_embed)

@bot.slash_command(name="choisir_personnage", description="Choisir un personnage pour le combat")
async def choose_character(ctx, nom_personnage: str):
    """Choisir un personnage pour le combat"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.respond("Aucun combat en cours dans ce canal!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if ctx.author.id not in [session.player1_id, session.player2_id]:
        await ctx.respond("Vous ne participez pas à ce combat!")
        return

    character = db.get_character(nom_personnage, ctx.author.id)
    if not character:
        await ctx.respond(f"Vous n'avez pas de personnage nommé **{nom_personnage}**.")
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

    for skill in character.skills:
        skill.cooldown = 0

    if ctx.author.id == session.player1_id:
        session.player1_character = character
    else:
        session.player2_character = character

    await ctx.respond(f"✅ **{nom_personnage}** sélectionné pour le combat!")

    if session.player1_character and session.player2_character:
        await start_objective_selection(ctx, session)

async def start_objective_selection(ctx, session):
    """Commencer la sélection des objectifs de victoire"""

    class ObjectiveSelect(discord.ui.Select):
        def __init__(self, user_id):
            self.user_id = user_id
            options = [
                discord.SelectOption(label="K.O.", description="Faire tomber l'adversaire KO (PV à 0)", value="1"),
                discord.SelectOption(label="Vider Pouvoir", description="Forcer l'adversaire à vider sa jauge de pouvoir", value="2"),
                discord.SelectOption(label="Bloodlust", description="Forcer l'adversaire à consommer son état de bloodlust", value="3")
            ]
            super().__init__(placeholder="Choisissez votre objectif...", options=options)

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("Ce n'est pas votre sélection!", ephemeral=True)
                return

            objective_map = {
                '1': ObjectifVictoire.KO,
                '2': ObjectifVictoire.VIDER_POUVOIR,
                '3': ObjectifVictoire.CONSOMMER_BLOODLUST
            }

            objective = objective_map[self.values[0]]

            if interaction.user.id == session.player1_id:
                session.player1_objective = objective
            else:
                session.player2_objective = objective

            await interaction.response.send_message(f"✅ Objectif sélectionné: **{objective.value}**")

            if session.both_players_ready():
                await start_rock_paper_scissors(ctx, session)

    class ObjectiveView(discord.ui.View):
        def __init__(self, user_id):
            super().__init__(timeout=60)
            self.add_item(ObjectiveSelect(user_id))

    objectives_embed = discord.Embed(
        title="🎯 Choix des Objectifs de Victoire",
        description="Chaque joueur doit choisir son objectif",
        color=0x00ff7f
    )

    player1 = bot.get_user(session.player1_id)
    player2 = bot.get_user(session.player2_id)

    await ctx.followup.send(f"{player1.mention}, choisissez votre objectif:", embed=objectives_embed, view=ObjectiveView(session.player1_id))
    await ctx.followup.send(f"{player2.mention}, choisissez votre objectif:", embed=objectives_embed, view=ObjectiveView(session.player2_id))

async def start_rock_paper_scissors(ctx, session):
    """Commencer le pierre-feuille-ciseaux pour déterminer l'ordre"""

    class RPSSelect(discord.ui.Select):
        def __init__(self, user_id):
            self.user_id = user_id
            options = [
                discord.SelectOption(label="Pierre", emoji="🪨", value="pierre"),
                discord.SelectOption(label="Feuille", emoji="📄", value="feuille"),
                discord.SelectOption(label="Ciseaux", emoji="✂️", value="ciseaux")
            ]
            super().__init__(placeholder="Choisissez...", options=options)

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("Ce n'est pas votre tour!", ephemeral=True)
                return

            session.rps_results[interaction.user.id] = self.values[0]
            await interaction.response.send_message("✅ Choix enregistré!", ephemeral=True)

            if len(session.rps_results) == 2:
                await resolve_rps(ctx, session)

    class RPSView(discord.ui.View):
        def __init__(self, user_id):
            super().__init__(timeout=60)
            self.add_item(RPSSelect(user_id))

    rps_embed = discord.Embed(
        title="✂️ Pierre-Feuille-Ciseaux",
        description="Choisissez pour déterminer l'ordre du combat",
        color=0xffff00
    )

    player1 = bot.get_user(session.player1_id)
    player2 = bot.get_user(session.player2_id)

    await ctx.followup.send(f"{player1.mention}", embed=rps_embed, view=RPSView(session.player1_id))
    await ctx.followup.send(f"{player2.mention}", embed=rps_embed, view=RPSView(session.player2_id))

async def resolve_rps(ctx, session):
    """Résoudre le pierre-feuille-ciseaux"""

    player1_choice = session.rps_results[session.player1_id]
    player2_choice = session.rps_results[session.player2_id]

    player1 = bot.get_user(session.player1_id)
    player2 = bot.get_user(session.player2_id)

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

        await ctx.followup.send(embed=result_embed)

        session.combat_started = True
        session.turn_count = 1
        await show_combat_status(ctx, session)
    else:
        result_embed.add_field(name="🤝 Égalité", value="Rejouez!", inline=False)
        session.rps_results.clear()
        await ctx.followup.send(embed=result_embed)
        await start_rock_paper_scissors(ctx, session)

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

    # Actions disponible via boutons
    class CombatView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)

        @discord.ui.button(label="Attaque", style=discord.ButtonStyle.red, emoji="⚔️")
        async def attack_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id != session.current_turn:
                await interaction.response.send_message("Ce n'est pas votre tour!", ephemeral=True)
                return

            await interaction.response.defer()
            await basic_attack_action(ctx, session, interaction.user.id)

        @discord.ui.button(label="Défense", style=discord.ButtonStyle.gray, emoji="🛡️")
        async def defense_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id != session.current_turn:
                await interaction.response.send_message("Ce n'est pas votre tour!", ephemeral=True)
                return

            await interaction.response.defer()
            await defense_action_handler(ctx, session, interaction.user.id)

        @discord.ui.button(label="Bloodlust", style=discord.ButtonStyle.danger, emoji="🔥")
        async def bloodlust_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id not in [session.player1_id, session.player2_id]:
                await interaction.response.send_message("Vous ne participez pas à ce combat!", ephemeral=True)
                return

            await interaction.response.defer()
            await bloodlust_action(ctx, session, interaction.user.id)

        @discord.ui.button(label="Forfait", style=discord.ButtonStyle.secondary, emoji="🏳️")
        async def forfeit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id not in [session.player1_id, session.player2_id]:
                await interaction.response.send_message("Vous ne participez pas à ce combat!", ephemeral=True)
                return

            await interaction.response.defer()
            winner_id = session.get_opponent_id(interaction.user.id)
            await interaction.followup.send(f"🏳️ **{interaction.user.display_name}** abandonne le combat!")
            await end_combat(ctx, session, winner_id)

    await ctx.followup.send(embed=embed, view=CombatView())

# Actions de combat (fonctions helpers)
async def basic_attack_action(ctx, session, user_id):
    attacker = session.get_character(user_id)
    defender = session.get_opponent_character(user_id)

    if attacker.skip_next_turn:
        attacker.skip_next_turn = False
        await ctx.followup.send(f"**{attacker.name}** doit sauter ce tour à cause d'une compétence restreinte!")
        await end_turn(ctx, session)
        return

    if attacker.bloodlust_turns > 0 and random.random() < 0.3:
        await ctx.followup.send(f"🔥 **{attacker.name}** en bloodlust agit de manière imprévisible!")
        # Action aléatoire simplifiée

    damage = combat_system.calculate_damage(attacker, defender)

    heal_amount = 0
    if attacker.bloodlust_turns > 0 and random.random() < 0.3:
        heal_amount = int(damage * 0.25)
        attacker.hp = min(attacker.max_hp, attacker.hp + heal_amount)

    defender.hp = max(0, defender.hp - damage)

    attack_msg = f"⚔️ **{attacker.name}** attaque **{defender.name}** pour **{damage}** dégâts!"
    if heal_amount > 0:
        attack_msg += f"\n💖 **{attacker.name}** récupère **{heal_amount}** PV grâce au bloodlust!"

    await ctx.followup.send(attack_msg)

    winner_id = combat_system.check_victory_conditions(session)
    if winner_id:
        await end_combat(ctx, session, winner_id)
        return

    await end_turn(ctx, session)

async def defense_action_handler(ctx, session, user_id):
    character = session.get_character(user_id)

    if character.skip_next_turn:
        character.skip_next_turn = False
        await ctx.followup.send(f"**{character.name}** doit sauter ce tour à cause d'une compétence restreinte!")
        await end_turn(ctx, session)
        return

    if character.defense_cooldown > 0:
        await ctx.followup.send(f"🛡️ Défense en cooldown ({character.defense_cooldown} tours restants)!")
        return

    character.defending = True
    await ctx.followup.send(f"🛡️ **{character.name}** se met en position de défense!")

    await end_turn(ctx, session)

async def bloodlust_action(ctx, session, user_id):
    character = session.get_character(user_id)

    if character.power_gauge > 0:
        await ctx.followup.send("Vous ne pouvez entrer en bloodlust qu'avec une jauge de pouvoir vide!")
        return

    if character.bloodlust_turns > 0:
        await ctx.followup.send("Vous êtes déjà en état de bloodlust!")
        return

    opponent_id = session.get_opponent_id(user_id)
    opponent_objective = session.player1_objective if opponent_id == session.player1_id else session.player2_objective

    if opponent_objective == ObjectifVictoire.VIDER_POUVOIR:
        await ctx.followup.send("❌ Vous ne pouvez pas entrer en bloodlust car c'est la condition de victoire de votre adversaire!")
        await end_combat(ctx, session, opponent_id)
        return

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

    await ctx.followup.send(embed=bloodlust_embed)
    await show_combat_status(ctx, session)

async def end_turn(ctx, session):
    current_char = session.get_character(session.current_turn)
    combat_system.process_turn_end(current_char)

    session.current_turn = session.get_opponent_id(session.current_turn)
    session.turn_count += 1

    await show_combat_status(ctx, session)

async def end_combat(ctx, session, winner_id: int):
    winner = bot.get_user(winner_id)
    loser_id = session.get_opponent_id(winner_id)
    loser = bot.get_user(loser_id)

    winner_char = session.get_character(winner_id)
    loser_char = session.get_character(loser_id)

    winner_exp = combat_system.calculate_experience(
        winner_char, 1000 - loser_char.hp, True, 
        winner_char.hp, winner_char.power_gauge
    )
    loser_exp = combat_system.calculate_experience(
        loser_char, 1000 - winner_char.hp, False,
        loser_char.hp, loser_char.power_gauge
    )

    winner_char.experience += winner_exp
    loser_char.experience += loser_exp

    winner_leveled = winner_char.can_level_up()
    loser_leveled = loser_char.can_level_up()

    if winner_leveled:
        winner_char.level_up()
    if loser_leveled:
        loser_char.level_up()

    winner_char.hp = winner_char.max_hp
    winner_char.power_gauge = 100.0
    loser_char.hp = loser_char.max_hp
    loser_char.power_gauge = 100.0

    db.update_character(winner_char)
    db.update_character(loser_char)

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

    await ctx.followup.send(embed=end_embed)

    del combat_system.active_combats[ctx.channel.id]

# Commandes slash pour les compétences
@bot.slash_command(name="competence", description="Utiliser une compétence en combat")
async def use_skill_command(ctx, nom_competence: str):
    """Utiliser une compétence"""

    if ctx.channel.id not in combat_system.active_combats:
        await ctx.respond("Aucun combat en cours!")
        return

    session = combat_system.active_combats[ctx.channel.id]

    if not session.combat_started:
        await ctx.respond("Le combat n'a pas encore commencé!")
        return

    if ctx.author.id != session.current_turn:
        await ctx.respond("Ce n'est pas votre tour!")
        return

    attacker = session.get_character(ctx.author.id)
    defender = session.get_opponent_character(ctx.author.id)

    if attacker.skip_next_turn:
        attacker.skip_next_turn = False
        await ctx.respond(f"**{attacker.name}** doit sauter ce tour à cause d'une compétence restreinte!")
        await end_turn(ctx, session)
        return

    skill = None
    for s in attacker.skills:
        if s.name.lower() == nom_competence.lower():
            skill = s
            break

    if not skill:
        await ctx.respond(f"Compétence **{nom_competence}** non trouvée!")
        return

    if skill.cooldown > 0:
        await ctx.respond(f"**{skill.name}** est en cooldown ({skill.cooldown} tours restants)!")
        return

    if attacker.power_gauge < skill.get_power_cost():
        await ctx.respond(f"Jauge de pouvoir insuffisante! (**{skill.get_power_cost()}%** requis)")
        return

    combat_system.use_skill(attacker, skill, defender)

    skill_msg = f"✨ **{attacker.name}** utilise **{skill.name}**!"

    damage = 0
    heal_amount = 0

    if skill.category in [SkillCategory.ATTAQUE, SkillCategory.RESTREINTE]:
        damage = combat_system.calculate_damage(attacker, defender, True, skill.category)

        if attacker.bloodlust_turns > 0 and random.random() < 0.3:
            heal_amount = int(damage * 0.25)
            attacker.hp = min(attacker.max_hp, attacker.hp + heal_amount)

        defender.hp = max(0, defender.hp - damage)
        skill_msg += f"\n💥 **{damage}** dégâts infligés!"

    if skill.category == SkillCategory.BONUS:
        skill_msg += "\n🔥 Prochaine attaque renforcée!"
    elif skill.category == SkillCategory.MALUS:
        skill_msg += "\n🛡️ Prochaine attaque adverse affaiblie!"
    elif skill.category == SkillCategory.RESTREINTE:
        skill_msg += "\n⏸️ L'adversaire sautera son prochain tour!"

    if heal_amount > 0:
        skill_msg += f"\n💖 **{attacker.name}** récupère **{heal_amount}** PV!"

    await ctx.respond(skill_msg)

    winner_id = combat_system.check_victory_conditions(session)
    if winner_id:
        await end_combat(ctx, session, winner_id)
        return

    await end_turn(ctx, session)

# Autres commandes slash utilitaires
@bot.slash_command(name="aide", description="Afficher toutes les commandes disponibles")
async def show_commands(ctx):
    """Afficher toutes les commandes disponibles"""

    embed = discord.Embed(
        title="🤖 Commandes du Bot RPG Discord",
        description="Voici toutes les commandes slash disponibles:",
        color=0x0099ff
    )

    embed.add_field(
        name="👤 Gestion des Personnages",
        value="`/creer_personnage` - Créer un personnage\n`/stats` - Voir les statistiques\n`/mes_personnages` - Lister vos personnages",
        inline=False
    )

    embed.add_field(
        name="⚔️ Combat",
        value="`/defier` - Défier un joueur\n`/choisir_personnage` - Choisir son personnage\n`/competence` - Utiliser une compétence",
        inline=False
    )

    embed.add_field(
        name="📊 Informations",
        value="Utilisez les boutons pendant les combats pour les actions (Attaque, Défense, Bloodlust, Forfait)",
        inline=False
    )

    await ctx.respond(embed=embed)

@bot.slash_command(name="classement", description="Afficher le classement des personnages")
async def leaderboard(ctx, critere: discord.Option(str, choices=["niveau", "experience"]) = "niveau"):
    """Afficher le classement des personnages"""

    cursor = db.conn.cursor()

    if critere == "niveau":
        cursor.execute("""
            SELECT name, owner_id, level, talent FROM characters 
            ORDER BY level DESC, experience DESC LIMIT 10
        """)
        title = "🏆 Classement par Niveau"
    else:
        cursor.execute("""
            SELECT name, owner_id, experience, talent FROM characters 
            ORDER BY experience DESC LIMIT 10
        """)
        title = "✨ Classement par Expérience"

    results = cursor.fetchall()

    if not results:
        await ctx.respond("Aucun personnage trouvé!")
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

    await ctx.respond(embed=embed)

if __name__ == "__main__":
    print("🚀 Démarrage du Bot RPG Discord avec commandes slash...")
    print("📝 N'oubliez pas de remplacer 'VOTRE_TOKEN_ICI' par votre vrai token Discord!")
    print("🔧 Commandes slash activées - utilisez / au lieu de !")

    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("❌ Erreur de connexion: Token Discord invalide!")
    except Exception as e:
        print(f"❌ Erreur lors du démarrage: {e}")
