import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from contextlib import contextmanager

# Configuration du logging
logger = logging.getLogger("docai.db_config")

# Récupération des variables d'environnement pour la connexion à PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://docai_user:docai_password@db:5432/docai_db")

def get_db_connection():
    """
    Établit et retourne une connexion à la base de données PostgreSQL.
    Cette fonction est utilisée comme dépendance dans FastAPI.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Erreur lors de la connexion à la base de données: {str(e)}")
        raise

@contextmanager
def get_db_cursor(commit=True):
    """
    Gestionnaire de contexte pour obtenir un curseur de base de données.
    Gère automatiquement la connexion, le commit et la fermeture.
    
    Exemple d'utilisation:
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM documents")
        results = cursor.fetchall()
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        yield cursor
        if commit:
            conn.commit()
    except Exception as e:
        if conn and commit:
            conn.rollback()
        logger.error(f"Erreur de base de données: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def init_db():
    """
    Initialise la base de données avec les tables nécessaires.
    Cette fonction est appelée au démarrage de l'application.
    """
    try:
        with get_db_cursor() as cursor:
            # Table des documents
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id VARCHAR(36) PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_path VARCHAR(512) NOT NULL,
                document_type VARCHAR(50) NOT NULL,
                upload_date TIMESTAMP NOT NULL,
                processed BOOLEAN DEFAULT FALSE,
                metadata JSONB
            )
            """)
            
            # Table des projets de code
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_projects (
                id VARCHAR(36) PRIMARY KEY,
                repo_url VARCHAR(512) NOT NULL,
                branch VARCHAR(100) NOT NULL,
                ingest_date TIMESTAMP NOT NULL,
                processed BOOLEAN DEFAULT FALSE,
                metadata JSONB
            )
            """)
            
            # Table de l'historique des chats
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(36),
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                metadata JSONB
            )
            """)
            
            # Table des retours d'utilisateurs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                query_id INTEGER REFERENCES chat_history(id),
                rating INTEGER NOT NULL,
                comments TEXT,
                timestamp TIMESTAMP NOT NULL
            )
            """)
            
            logger.info("Base de données initialisée avec succès.")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base de données: {str(e)}")
        raise

# Fonction pour vérifier la connexion à la base de données
def check_db_connection():
    """
    Vérifie si la connexion à la base de données est fonctionnelle.
    Retourne True si la connexion est établie, False sinon.
    """
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error(f"Échec de la vérification de connexion à la base de données: {str(e)}")
        return False
