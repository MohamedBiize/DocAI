from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os
import uuid
from datetime import datetime
import logging

from app.db_config import get_db_connection
from app.rag_pipeline import RAGPipeline

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("docai")

# Initialisation de l'application FastAPI
app = FastAPI(
    title="DocAI API",
    description="API pour l'agent IA DocAI de MedYouIN basé sur une architecture RAG",
    version="0.1.0",
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À remplacer par les domaines spécifiques en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisation du pipeline RAG
rag_pipeline = RAGPipeline()

# Dossier pour les téléchargements temporaires
TEMP_UPLOAD_DIR = "/app/data/temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

# Routes API
@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API DocAI de MedYouIN"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    document_type: str = "internal",
    conn = Depends(get_db_connection)
):
    """
    Télécharge et traite des documents (PDF, Markdown, DOCX)
    """
    uploaded_files = []
    
    try:
        for file in files:
            # Vérification de l'extension
            if not file.filename.lower().endswith(('.pdf', '.md', '.docx')):
                raise HTTPException(status_code=400, detail=f"Format de fichier non supporté: {file.filename}")
            
            # Génération d'un ID unique pour le fichier
            file_id = str(uuid.uuid4())
            file_path = os.path.join(TEMP_UPLOAD_DIR, f"{file_id}_{file.filename}")
            
            # Sauvegarde du fichier
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Enregistrement des métadonnées dans la base de données
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (id, filename, file_path, document_type, upload_date) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (file_id, file.filename, file_path, document_type, datetime.now())
            )
            conn.commit()
            
            # Ajout du traitement en tâche de fond
            background_tasks.add_task(rag_pipeline.process_document, file_path, file_id, document_type)
            
            uploaded_files.append({"file_id": file_id, "filename": file.filename})
        
        return {"message": "Documents téléchargés avec succès", "files": uploaded_files}
    
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement des documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du téléchargement: {str(e)}")

@app.post("/query")
async def query_documents(
    query: str,
    temp_files: Optional[List[UploadFile]] = File(None),
    conn = Depends(get_db_connection)
):
    """
    Interroge les documents avec une question et retourne une réponse basée sur le contenu
    """
    try:
        # Traitement des fichiers temporaires si fournis
        temp_file_paths = []
        if temp_files:
            for file in temp_files:
                file_path = os.path.join(TEMP_UPLOAD_DIR, f"temp_{uuid.uuid4()}_{file.filename}")
                with open(file_path, "wb") as f:
                    content = await file.read()
                    f.write(content)
                temp_file_paths.append(file_path)
        
        # Interrogation du pipeline RAG
        response = rag_pipeline.query(query, temp_file_paths)
        
        # Enregistrement de l'historique de chat
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (query, response, timestamp) VALUES (%s, %s, %s)",
            (query, response, datetime.now())
        )
        conn.commit()
        
        return {"query": query, "response": response}
    
    except Exception as e:
        logger.error(f"Erreur lors de la requête: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la requête: {str(e)}")

@app.post("/code/ingest")
async def ingest_github_code(
    background_tasks: BackgroundTasks,
    repo_url: str,
    branch: str = "main",
    conn = Depends(get_db_connection)
):
    """
    Ingère le code d'un projet GitHub
    """
    try:
        # Génération d'un ID unique pour le projet
        project_id = str(uuid.uuid4())
        
        # Enregistrement des métadonnées dans la base de données
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO code_projects (id, repo_url, branch, ingest_date) VALUES (%s, %s, %s, %s) RETURNING id",
            (project_id, repo_url, branch, datetime.now())
        )
        conn.commit()
        
        # Ajout du traitement en tâche de fond
        background_tasks.add_task(rag_pipeline.process_github_repo, repo_url, branch, project_id)
        
        return {"message": "Ingestion du code GitHub initiée", "project_id": project_id}
    
    except Exception as e:
        logger.error(f"Erreur lors de l'ingestion du code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'ingestion du code: {str(e)}")

@app.post("/feedback")
async def submit_feedback(
    query_id: str,
    rating: int,
    comments: Optional[str] = None,
    conn = Depends(get_db_connection)
):
    """
    Soumet un retour d'utilisateur sur une réponse
    """
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO feedback (query_id, rating, comments, timestamp) VALUES (%s, %s, %s, %s)",
            (query_id, rating, comments, datetime.now())
        )
        conn.commit()
        
        return {"message": "Feedback enregistré avec succès"}
    
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'enregistrement du feedback: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
