import os
import logging
from typing import List, Dict, Any, Optional
import uuid
import json
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, HttpUrl

from app.db_config import get_db_connection
from app.rag_pipeline import RAGPipeline

# Configuration du logging
logger = logging.getLogger("docai.api.github")

# Initialisation du router FastAPI
router = APIRouter(prefix="/github", tags=["GitHub"])

# Modèles Pydantic
class GitHubIngestRequest(BaseModel):
    repo_url: HttpUrl
    branch: str = "main"
    description: Optional[str] = None
    user_id: Optional[str] = None

class GitHubIngestResponse(BaseModel):
    message: str
    project_id: str
    status: str = "processing"

class GitHubQueryRequest(BaseModel):
    question: str
    repo_url: Optional[HttpUrl] = None
    project_id: Optional[str] = None
    user_id: Optional[str] = None

class GitHubQueryResponse(BaseModel):
    answer: str
    source_documents: List[Dict[str, Any]]

# Référence au pipeline RAG
rag_pipeline = None

def initialize(pipeline: RAGPipeline):
    """
    Initialise le module avec une référence au pipeline RAG.
    
    Args:
        pipeline: Instance du RAGPipeline
    """
    global rag_pipeline
    rag_pipeline = pipeline
    logger.info("Module API GitHub initialisé")

@router.post("/ingest", response_model=GitHubIngestResponse)
async def ingest_github_repo(
    request: GitHubIngestRequest,
    background_tasks: BackgroundTasks,
    conn = Depends(get_db_connection)
):
    """
    Lance l'ingestion d'un dépôt GitHub en tâche de fond.
    
    Args:
        request: Requête d'ingestion contenant l'URL du dépôt et la branche
        background_tasks: Gestionnaire de tâches en arrière-plan FastAPI
        conn: Connexion à la base de données
        
    Returns:
        Réponse contenant l'ID du projet et le statut
    """
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="Le service RAG n'est pas disponible")
    
    logger.info(f"Requête d'ingestion GitHub reçue: {request.repo_url} (branche: {request.branch})")
    
    # Générer un ID unique pour le projet
    project_id = str(uuid.uuid4())
    
    try:
        # Enregistrer les métadonnées du projet dans la base de données
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO code_projects 
            (id, repo_url, branch, ingest_date, processed, metadata) 
            VALUES (%s, %s, %s, NOW(), %s, %s) 
            RETURNING id
            """,
            (
                project_id, 
                str(request.repo_url), 
                request.branch, 
                False, 
                json.dumps({
                    "description": request.description,
                    "user_id": request.user_id
                })
            )
        )
        conn.commit()
        logger.info(f"Projet GitHub enregistré dans la base de données (ID: {project_id})")
        
        # Lancer l'ingestion en tâche de fond
        background_tasks.add_task(
            process_github_repo_background, 
            project_id, 
            str(request.repo_url), 
            request.branch, 
            conn
        )
        
        return {
            "message": "Ingestion du dépôt GitHub initiée",
            "project_id": project_id,
            "status": "processing"
        }
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur lors de l'initiation de l'ingestion GitHub: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'initiation de l'ingestion: {str(e)}")
    
    finally:
        if 'cursor' in locals() and not cursor.closed:
            cursor.close()

@router.post("/query", response_model=GitHubQueryResponse)
async def query_github_code(
    request: GitHubQueryRequest,
    conn = Depends(get_db_connection)
):
    """
    Interroge le code source GitHub indexé.
    
    Args:
        request: Requête contenant la question et optionnellement l'URL du dépôt ou l'ID du projet
        conn: Connexion à la base de données
        
    Returns:
        Réponse contenant la réponse générée et les documents sources
    """
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="Le service RAG n'est pas disponible")
    
    logger.info(f"Requête de question sur le code GitHub reçue: '{request.question}'")
    
    try:
        # Construire le filtre de métadonnées
        filter_metadata = {"source_type": "code"}
        
        # Ajouter des filtres supplémentaires si spécifiés
        if request.repo_url:
            filter_metadata["repo_url"] = str(request.repo_url)
        
        if request.project_id:
            filter_metadata["project_id"] = request.project_id
        
        # Interroger le pipeline RAG avec le filtre
        result = rag_pipeline.query(request.question, filter_metadata=filter_metadata)
        
        # Enregistrer l'historique de chat dans la base de données
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_history 
                (user_id, query, response, timestamp, metadata) 
                VALUES (%s, %s, %s, NOW(), %s) 
                RETURNING id
                """,
                (
                    request.user_id, 
                    request.question, 
                    result["answer"], 
                    json.dumps({
                        "source_type": "code",
                        "repo_url": str(request.repo_url) if request.repo_url else None,
                        "project_id": request.project_id
                    })
                )
            )
            conn.commit()
            logger.info("Historique de chat enregistré dans la base de données")
        
        except Exception as db_err:
            conn.rollback()
            logger.error(f"Erreur lors de l'enregistrement de l'historique de chat: {db_err}")
            # Continuer malgré l'erreur d'enregistrement
        
        finally:
            if 'cursor' in locals() and not cursor.closed:
                cursor.close()
        
        return result
    
    except Exception as e:
        logger.error(f"Erreur lors de la requête sur le code GitHub: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la requête: {str(e)}")

async def process_github_repo_background(project_id: str, repo_url: str, branch: str, conn):
    """
    Fonction de traitement en arrière-plan pour l'ingestion d'un dépôt GitHub.
    
    Args:
        project_id: ID unique du projet
        repo_url: URL du dépôt GitHub
        branch: Branche à cloner
        conn: Connexion à la base de données
    """
    logger.info(f"Démarrage du traitement en arrière-plan pour le dépôt GitHub: {repo_url} (ID: {project_id})")
    
    try:
        # Traiter le dépôt GitHub
        num_documents = rag_pipeline.process_github_repo(repo_url, branch, project_id)
        
        # Mettre à jour le statut dans la base de données
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE code_projects 
            SET processed = %s, metadata = jsonb_set(metadata, '{num_documents}', %s) 
            WHERE id = %s
            """,
            (True, json.dumps(num_documents), project_id)
        )
        conn.commit()
        logger.info(f"Traitement du dépôt GitHub terminé: {num_documents} documents indexés (ID: {project_id})")
    
    except Exception as e:
        # Enregistrer l'erreur dans la base de données
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE code_projects 
                SET metadata = jsonb_set(metadata, '{error}', %s) 
                WHERE id = %s
                """,
                (json.dumps(str(e)), project_id)
            )
            conn.commit()
        except Exception as db_err:
            logger.error(f"Erreur lors de la mise à jour du statut d'erreur dans la base de données: {db_err}")
        
        logger.error(f"Erreur lors du traitement du dépôt GitHub {repo_url} (ID: {project_id}): {e}", exc_info=True)
    
    finally:
        if 'cursor' in locals() and not cursor.closed:
            cursor.close()
