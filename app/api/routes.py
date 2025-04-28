from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from typing import List, Optional
from datetime import datetime
import uuid
import os

from app.core.rag_pipeline import RAGPipeline
from app.core.db_config import get_db_connection
from app.models.schemas import (
    AskRequest,
    AskResponse,
    UploadResponse,
    IngestCodeRequest,
    IngestCodeResponse,
    FeedbackRequest,
    FeedbackResponse
)

router = APIRouter()

@router.get("/")
async def root():
    return {"message": "Welcome to DocAI API"}

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    document_type: str = "internal",
    conn = Depends(get_db_connection)
):
    """
    Upload one or more documents (PDF, Markdown, DOCX) and process them
    in the background for RAG ingestion.
    """
    uploaded_files_info = []
    
    for file in files:
        file_id = str(uuid.uuid4())
        safe_filename = f"{file_id}_{file.filename}"
        file_path = os.path.join(os.getenv("TEMP_UPLOAD_DIR"), safe_filename)
        
        try:
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (id, filename, file_path, document_type, upload_date, processed) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (file_id, file.filename, file_path, document_type, datetime.now(), False)
            )
            inserted_id = cursor.fetchone()[0]
            conn.commit()
            
            background_tasks.add_task(
                RAGPipeline().process_document,
                file_path,
                document_id=file_id,
                metadata={"document_type": document_type}
            )
            
            uploaded_files_info.append({
                "file_id": file_id,
                "filename": file.filename,
                "status": "processing_queued"
            })
            
        except Exception as e:
            conn.rollback()
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            if 'cursor' in locals() and not cursor.closed:
                cursor.close()

    return {"message": "Documents received and queued for processing.", "files": uploaded_files_info}

@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    conn = Depends(get_db_connection)
):
    """
    Process a user question through the RAG pipeline and return the response.
    """
    try:
        rag_result = RAGPipeline().query(request.question)
        answer = rag_result["answer"]
        source_documents = rag_result["source_documents"]
        
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (user_id, query, response, timestamp, metadata) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (request.user_id, request.question, answer, datetime.now(), None)
        )
        chat_id = cursor.fetchone()[0]
        conn.commit()
        
        return {"answer": answer, "source_documents": source_documents}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cursor' in locals() and not cursor.closed:
            cursor.close()

@router.post("/code/ingest", response_model=IngestCodeResponse)
async def ingest_github_code(
    request: IngestCodeRequest,
    background_tasks: BackgroundTasks,
    conn = Depends(get_db_connection)
):
    """
    Ingest code from a GitHub repository in the background.
    """
    project_id = str(uuid.uuid4())
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (id, repo_url, branch, status, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (project_id, request.repo_url, request.branch, "queued", datetime.now())
        )
        conn.commit()
        
        background_tasks.add_task(
            RAGPipeline().ingest_github_repo,
            request.repo_url,
            request.branch,
            project_id
        )
        
        return {"message": "Code ingestion queued", "project_id": project_id}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cursor' in locals() and not cursor.closed:
            cursor.close()

@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    conn = Depends(get_db_connection)
):
    """
    Submit feedback for a specific query response.
    """
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO feedback (query_id, rating, comments, user_id, timestamp) VALUES (%s, %s, %s, %s, %s)",
            (request.query_id, request.rating, request.comments, request.user_id, datetime.now())
        )
        conn.commit()
        return {"message": "Feedback submitted successfully"}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cursor' in locals() and not cursor.closed:
            cursor.close() 