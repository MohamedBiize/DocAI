from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid
from datetime import datetime
import logging

from app.db_config import get_db_connection, init_db, check_db_connection
from app.rag_pipeline import RAGPipeline

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
)
logger = logging.getLogger("docai.main")

# --- Initialisation --- 

# Créer les dossiers nécessaires si absents
TEMP_UPLOAD_DIR = "/app/data/temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

# Initialiser la base de données au démarrage (si nécessaire)
try:
    if check_db_connection():
        init_db() # Crée les tables si elles n'existent pas
    else:
        logger.error("Échec de la connexion à la base de données au démarrage. L'initialisation de la DB est ignorée.")
except Exception as e:
    logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")

# Initialisation du pipeline RAG (après la configuration potentielle des clés API)
# Assurez-vous que les variables d'environnement (ex: OPENAI_API_KEY) sont définies
# avant cette étape si vous utilisez des modèles non factices.
try:
    rag_pipeline = RAGPipeline()
except Exception as e:
    logger.critical(f"Échec de l'initialisation du RAGPipeline: {e}", exc_info=True)
    # Gérer l'échec de manière appropriée, peut-être arrêter l'application
    # ou fonctionner en mode dégradé si possible.
    rag_pipeline = None # Indique que le pipeline n'est pas fonctionnel

# Initialisation de l'application FastAPI
app = FastAPI(
    title="DocAI API",
    description="API pour l'agent IA DocAI de MedYouIN basé sur une architecture RAG",
    version="0.2.0", # Version mise à jour
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Modèles Pydantic --- 

class AskRequest(BaseModel):
    question: str
    user_id: Optional[str] = None # Pour un suivi futur

class AskResponse(BaseModel):
    answer: str
    source_documents: List[dict] # Liste de dictionnaires contenant les métadonnées et le contenu

class UploadResponse(BaseModel):
    message: str
    files: List[dict]

class IngestCodeRequest(BaseModel):
    repo_url: str
    branch: str = "main"

class IngestCodeResponse(BaseModel):
    message: str
    project_id: str

class FeedbackRequest(BaseModel):
    query_id: int # Référence l'ID de chat_history
    rating: int # Ex: 1 à 5
    comments: Optional[str] = None
    user_id: Optional[str] = None

class FeedbackResponse(BaseModel):
    message: str

# --- Routes API --- 

@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API DocAI de MedYouIN"}

@app.get("/health")
async def health_check():
    db_status = "healthy" if check_db_connection() else "unhealthy"
    rag_status = "initialized" if rag_pipeline else "failed_initialization"
    return {
        "status": "healthy" if db_status == "healthy" and rag_status == "initialized" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "dependencies": {
            "database": db_status,
            "rag_pipeline": rag_status
        }
    }

@app.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    document_type: str = "internal", # Ex: 'internal', 'user_temp'
    conn = Depends(get_db_connection)
):
    """
    Télécharge un ou plusieurs documents (PDF, Markdown, DOCX) et lance
    leur traitement en arrière-plan pour ingestion dans le RAG.
    """
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="Le service RAG n'est pas disponible.")
        
    uploaded_files_info = []
    
    for file in files:
        # Vérification de l'extension
        allowed_extensions = (".pdf", ".md", ".txt", ".docx")
        if not file.filename.lower().endswith(allowed_extensions):
            logger.warning(f"Tentative de téléchargement d'un format non supporté: {file.filename}")
            # On pourrait choisir d'ignorer ce fichier ou de lever une erreur pour tout le lot
            # Ici, on lève une exception pour être strict
            raise HTTPException(status_code=400, detail=f"Format de fichier non supporté: {file.filename}. Extensions autorisées: {allowed_extensions}")
        
        file_id = str(uuid.uuid4())
        # Utiliser un nom de fichier unique pour éviter les collisions
        safe_filename = f"{file_id}_{file.filename}"
        file_path = os.path.join(TEMP_UPLOAD_DIR, safe_filename)
        
        try:
            # Sauvegarde du fichier sur le disque
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            logger.info(f"Fichier temporaire sauvegardé: {file_path}")

            # Enregistrement initial dans la base de données
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (id, filename, file_path, document_type, upload_date, processed) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (file_id, file.filename, file_path, document_type, datetime.now(), False)
            )
            inserted_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            logger.info(f"Métadonnées du document enregistrées dans la DB (ID: {inserted_id})")

            # Ajout du traitement RAG en tâche de fond
            metadata_for_rag = {"document_type": document_type}
            background_tasks.add_task(rag_pipeline.process_document, file_path, document_id=file_id, metadata=metadata_for_rag)
            logger.info(f"Tâche d'ingestion RAG ajoutée pour le document ID: {file_id}")
            
            uploaded_files_info.append({"file_id": file_id, "filename": file.filename, "status": "processing_queued"})
        
        except Exception as e:
            conn.rollback() # Annuler la transaction DB si erreur après l'insertion
            logger.error(f"Erreur lors du traitement du fichier {file.filename}: {str(e)}", exc_info=True)
            # Nettoyer le fichier sauvegardé si une erreur survient
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as rm_err:
                    logger.error(f"Impossible de supprimer le fichier temporaire {file_path} après erreur: {rm_err}")
            # Renvoyer une erreur HTTP
            raise HTTPException(status_code=500, detail=f"Erreur interne lors du traitement du fichier {file.filename}.")
        finally:
            if 'cursor' in locals() and not cursor.closed:
                cursor.close()

    return {"message": "Documents reçus et mis en file d'attente pour traitement.", "files": uploaded_files_info}

@app.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    conn = Depends(get_db_connection)
):
    """
    Reçoit une question utilisateur, interroge le pipeline RAG,
    enregistre la conversation et retourne la réponse générée.
    """
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="Le service RAG n'est pas disponible.")
        
    logger.info(f"Requête reçue sur /ask: Question='{request.question}', UserID='{request.user_id}'")
    
    try:
        # Interrogation du pipeline RAG
        rag_result = rag_pipeline.query(request.question)
        answer = rag_result["answer"]
        source_documents = rag_result["source_documents"]
        
        # Enregistrement de l'historique de chat dans la base de données
        chat_id = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_history (user_id, query, response, timestamp, metadata) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (request.user_id, request.question, answer, datetime.now(), None) # Ajouter des métadonnées si nécessaire
            )
            chat_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Historique de chat enregistré (ID: {chat_id})")
        except Exception as db_err:
            conn.rollback()
            logger.error(f"Erreur lors de l'enregistrement de l'historique de chat: {db_err}", exc_info=True)
            # Continuer même si l'historique ne peut pas être sauvegardé ? Ou lever une erreur ?
            # Pour l'instant, on log l'erreur mais on renvoie quand même la réponse.
        finally:
            if 'cursor' in locals() and not cursor.closed:
                cursor.close()

        # Retourner la réponse structurée
        return {"answer": answer, "source_documents": source_documents}
    
    except Exception as e:
        logger.error(f"Erreur lors de la requête RAG pour la question '{request.question}': {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne lors de la génération de la réponse.")

@app.post("/code/ingest", response_model=IngestCodeResponse)
async def ingest_github_code(
    request: IngestCodeRequest,
    background_tasks: BackgroundTasks,
    conn = Depends(get_db_connection)
):
    """
    Lance l'ingestion du code d'un projet GitHub en arrière-plan.
    (Note: La logique d'ingestion dans rag_pipeline est un placeholder).
    """
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="Le service RAG n'est pas disponible.")
        
    logger.info(f"Requête reçue sur /code/ingest: Repo='{request.repo_url}', Branch='{request.branch}'")
    project_id = str(uuid.uuid4())
    
    try:
        # Enregistrement initial dans la base de données
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO code_projects (id, repo_url, branch, ingest_date, processed) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (project_id, request.repo_url, request.branch, datetime.now(), False)
        )
        inserted_id = cursor.fetchone()[0]
        conn.commit()
        logger.info(f"Métadonnées du projet code enregistrées dans la DB (ID: {inserted_id})")

        # Ajout du traitement RAG en tâche de fond (placeholder)
        background_tasks.add_task(rag_pipeline.process_github_repo, request.repo_url, request.branch, project_id)
        logger.info(f"Tâche d'ingestion de code GitHub ajoutée pour le projet ID: {project_id}")
        
        return {"message": "Ingestion du code GitHub initiée (implémentation placeholder).", "project_id": project_id}
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur lors de l'initiation de l'ingestion du code pour {request.repo_url}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne lors de l'initiation de l'ingestion du code.")
    finally:
        if 'cursor' in locals() and not cursor.closed:
            cursor.close()

@app.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    conn = Depends(get_db_connection)
):
    """
    Enregistre le retour d'un utilisateur sur une réponse spécifique.
    """
    logger.info(f"Feedback reçu: QueryID={request.query_id}, Rating={request.rating}, UserID={request.user_id}")
    try:
        cursor = conn.cursor()
        # Vérifier si query_id existe dans chat_history (optionnel mais recommandé)
        cursor.execute("SELECT id FROM chat_history WHERE id = %s", (request.query_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail=f"L'ID de chat {request.query_id} n'existe pas.")
            
        cursor.execute(
            "INSERT INTO feedback (query_id, rating, comments, timestamp, user_id) VALUES (%s, %s, %s, %s, %s)",
            (request.query_id, request.rating, request.comments, datetime.now(), request.user_id)
        )
        conn.commit()
        logger.info(f"Feedback enregistré pour QueryID: {request.query_id}")
        return {"message": "Feedback enregistré avec succès"}
    
    except HTTPException as http_exc:
        conn.rollback()
        raise http_exc # Renvoyer l'exception HTTP telle quelle
    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur lors de l'enregistrement du feedback pour QueryID {request.query_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne lors de l'enregistrement du feedback.")
    finally:
        if 'cursor' in locals() and not cursor.closed:
            cursor.close()

# --- Démarrage de l'application (pour exécution directe) --- 
if __name__ == "__main__":
    # Ceci est utile pour le développement local sans uvicorn en ligne de commande
    # En production, utilisez un serveur ASGI comme uvicorn ou hypercorn directement
    import uvicorn
    logger.info("Démarrage du serveur FastAPI en mode développement...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
