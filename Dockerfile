# Utiliser une image officielle Python basée sur Debian (évite Alpine minimaliste)
FROM python:3.11-slim

# Mettre à jour pip et installer les dépendances système nécessaires (libffi, gcc, etc. si besoin)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de votre projet
WORKDIR /app
COPY . /app

# Installer les dépendances Python depuis requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Commande pour lancer le bot
CMD ["python", "discord_rpg_bot_complet.py"]
