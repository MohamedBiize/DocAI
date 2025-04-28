import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/docai")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "/app/data/chroma")

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # or "gemini" or "deepseek"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# GitHub Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

# File Storage
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/data/uploads")
TEMP_UPLOAD_DIR = os.getenv("TEMP_UPLOAD_DIR", "/app/data/temp_uploads")

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"

# Validate required environment variables
def validate_env():
    required_vars = {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "GITHUB_TOKEN": GITHUB_TOKEN,
        "SECRET_KEY": SECRET_KEY
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Validate environment on import
validate_env() 