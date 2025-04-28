FROM python:3.10-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copie des fichiers de dépendances
COPY ./app/requirements.txt /app/requirements.txt

# Installation des dépendances Python
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copie du code de l'application
COPY ./app /app/

# Exposition du port pour FastAPI
EXPOSE 8000

# Commande de démarrage
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
