from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.routes import router as api_router
from app.core.db_config import init_db, check_db_connection
from app.core.rag_pipeline import RAGPipeline
from config.settings import (
    DEBUG,
    ALLOWED_ORIGINS,
    LOG_LEVEL,
    LOG_FORMAT
)

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
)
logger = logging.getLogger("docai.main")

# Initialize FastAPI app
app = FastAPI(
    title="DocAI API",
    description="API for the DocAI intelligent document assistant",
    version="0.2.0",
    debug=DEBUG
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database and RAG pipeline
@app.on_event("startup")
async def startup_event():
    try:
        if check_db_connection():
            init_db()
            logger.info("Database initialized successfully")
        else:
            logger.error("Failed to connect to database during startup")
    except Exception as e:
        logger.error(f"Error during startup: {e}")

    try:
        RAGPipeline()
        logger.info("RAG pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG pipeline: {e}")

# Include API routes
app.include_router(api_router, prefix="/api/v1")
