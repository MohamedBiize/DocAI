from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class AskRequest(BaseModel):
    question: str
    user_id: Optional[str] = None

class AskResponse(BaseModel):
    answer: str
    source_documents: List[dict]

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
    query_id: int
    rating: int
    comments: Optional[str] = None
    user_id: Optional[str] = None

class FeedbackResponse(BaseModel):
    message: str

class Document(BaseModel):
    id: str
    filename: str
    file_path: str
    document_type: str
    upload_date: datetime
    processed: bool

class Project(BaseModel):
    id: str
    repo_url: str
    branch: str
    status: str
    created_at: datetime

class ChatHistory(BaseModel):
    id: int
    user_id: Optional[str]
    query: str
    response: str
    timestamp: datetime
    metadata: Optional[dict]

class Feedback(BaseModel):
    id: int
    query_id: int
    rating: int
    comments: Optional[str]
    user_id: Optional[str]
    timestamp: datetime 