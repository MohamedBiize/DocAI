# DocAI - Intelligent Document Assistant

DocAI is an AI assistant based on RAG (Retrieval-Augmented Generation) technology, designed to help internal users access company knowledge more efficiently.

## 🎯 Project Goals

- Build an interactive AI agent that answers questions using internal documentation and code
- Automate tasks like preparing documents for bids (appels d'offres)
- Provide transparent answers by showing sources (documents or code parts)

## ✨ Key Features

- Chat (general + project-specific chat)
- Document upload (PDF, images, Markdown)
- GitHub integration (code parsing and indexing)
- Admin dashboard (statistics, frequent questions)
- User authentication
- Feedback system
- Slack integration
- Chat history export as PDFs

## 🛠️ Technical Stack

- **Backend**: FastAPI
- **Database**: PostgreSQL
- **Vector Store**: ChromaDB
- **AI/LLM**: LangChain + (Gemini 2.5 Pro or DeepSeek R1)
- **Deployment**: Docker

## 📋 Project Status

### ✅ Completed Phases

1. **Project Initialization**
   - Project structure created
   - Docker configuration with FastAPI, PostgreSQL, and ChromaDB
   - Local deployment ready

2. **Document RAG Pipeline**
   - File ingestion (PDF, Markdown, DOCX)
   - Chunking and embedding
   - ChromaDB indexing
   - API endpoints for document querying
   - Test scripts implemented

3. **GitHub Code Integration**
   - Automatic repository cloning
   - Code source parsing (functions, classes, methods)
   - Code storage in ChromaDB with metadata
   - GitHub-specific API endpoints
   - Dedicated test scripts

### 🚧 Current Status

| Component | Status |
|-----------|--------|
| Document Ingestion | ✅ Functional |
| Source Code Ingestion | ✅ Functional |
| Intelligent Questioning | ✅ Functional |
| Docker Infrastructure | ✅ Ready |
| Git Versioning | ✅ Structured |

## 📅 Project Milestones

1. **Basic Agent Setup**
   - [ ] Create prototype with MedYouIN documents
   - [ ] Implement basic RAG pipeline
   - [ ] Set up initial document corpus

2. **GitHub Integration**
   - [ ] Code retrieval system
   - [ ] Code analysis and indexing
   - [ ] Code-specific querying

3. **Attachment Management**
   - [ ] File upload system
   - [ ] Document processing pipeline
   - [ ] Storage and retrieval system

4. **Model Actions & Data Logging**
   - [ ] Email integration
   - [ ] Chat history management
   - [ ] User interaction tracking

5. **Bid Document Analysis**
   - [ ] Document analysis pipeline
   - [ ] Response generation
   - [ ] Document preparation tools

6. **Frontend and Authentication**
   - [ ] Web interface development
   - [ ] User authentication system
   - [ ] Session management

7. **Admin Dashboard**
   - [ ] Usage statistics
   - [ ] System monitoring
   - [ ] User management

8. **Advanced Features**
   - [ ] Slack integration
   - [ ] Feedback collection
   - [ ] Export functionality

## 🚀 Getting Started

1. Clone the repository
2. Set up environment variables
3. Run `docker-compose up --build`
4. Access the API at `http://localhost:8000`

## 📝 Documentation

- API documentation available at `/docs` when running the server
- Test scripts available in the `tests/` directory
- Configuration files in `config/`

## 🤝 Contributing

Please read our contributing guidelines before submitting pull requests.

## 📄 License

This project is proprietary and confidential. 