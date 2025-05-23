import os
import logging
import chromadb
from chromadb.config import Settings
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, OpenAI # Placeholder models
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from typing import List, Dict, Any, Optional
import uuid
import time

# Import du module d'ingestion GitHub
from app.github_ingestion import GitHubIngestion

# Configuration du logging
logger = logging.getLogger("docai.rag_pipeline")
logging.basicConfig(level=logging.INFO)

# --- Configuration --- 
# Utiliser les variables d'environnement pour plus de flexibilité
CHROMA_HOST = os.getenv("CHROMA_HOST", "chroma")
CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")
# Pour une persistance locale lors du développement hors Docker, décommentez :
# CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "/home/ubuntu/docai/db_data/chroma_persist") 
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "docai_collection")
# Gérer la clé API OpenAI via les variables d'environnement
# os.environ["OPENAI_API_KEY"] = "votre_cle_api_ici" 

class RAGPipeline:
    """
    Implémente la logique de Retrieval-Augmented Generation (RAG).
    Gère l'ingestion de documents, l'indexation dans ChromaDB,
    et la réponse aux requêtes utilisateur en utilisant LangChain.
    """
    def __init__(self):
        logger.info("Initialisation du pipeline RAG...")
        try:
            # Initialisation du client ChromaDB
            # Utilisation de HttpClient pour se connecter au service Chroma dans Docker
            self.chroma_client = chromadb.HttpClient(
                host=CHROMA_HOST,
                port=CHROMA_PORT,
                settings=Settings(allow_reset=True) # Permet la réinitialisation si nécessaire
            )
            # Pour une persistance locale hors Docker, utilisez :
            # self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
            
            # Vérification et création de la collection si elle n'existe pas
            try:
                self.collection = self.chroma_client.get_collection(COLLECTION_NAME)
                logger.info(f"Collection ChromaDB '{COLLECTION_NAME}' existante trouvée.")
            except Exception: # Adaptez l'exception spécifique si connue
                logger.info(f"Collection ChromaDB '{COLLECTION_NAME}' non trouvée, création en cours...")
                self.collection = self.chroma_client.create_collection(COLLECTION_NAME)
                logger.info(f"Collection ChromaDB '{COLLECTION_NAME}' créée.")

            # --- Placeholders pour les modèles --- 
            # Remplacez par les modèles souhaités (Gemini, DeepSeek, etc.)
            # Assurez-vous que les intégrations LangChain correspondantes sont installées
            # et que les clés API/configurations sont gérées de manière sécurisée.
            if not os.getenv("OPENAI_API_KEY"):
                logger.warning("Clé API OpenAI non définie. Utilisation de modèles factices.")
                # Utiliser des modèles factices si la clé n'est pas définie
                from langchain.embeddings.fake import FakeEmbeddings
                from langchain.llms.fake import FakeListLLM
                self.embeddings = FakeEmbeddings(size=768) # Taille d'embedding factice
                responses = ["Réponse factice 1", "Réponse factice 2"]
                self.llm = FakeListLLM(responses=responses)
            else:
                self.embeddings = OpenAIEmbeddings() 
                self.llm = OpenAI()
            # --- Fin Placeholders --- 

            # Initialisation du Vector Store LangChain avec Chroma
            self.vector_store = Chroma(
                client=self.chroma_client,
                collection_name=COLLECTION_NAME,
                embedding_function=self.embeddings
            )
            
            # Initialisation du Text Splitter
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                add_start_index=True, # Utile pour référencer la source
            )
            
            # Initialisation de la chaîne RetrievalQA
            # 'stuff' est simple mais peut dépasser la limite de contexte pour de nombreux documents.
            # Envisagez 'map_reduce', 'refine', ou 'map_rerank' pour des cas plus complexes.
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff", 
                retriever=self.vector_store.as_retriever(search_kwargs={"k": 3}), # Récupère les 3 chunks les plus pertinents
                return_source_documents=True # Retourne les documents sources pour référence
            )
            
            # Initialisation du module d'ingestion GitHub
            self.github_ingestion = GitHubIngestion()
            
            logger.info("Pipeline RAG initialisé avec succès.")

        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du pipeline RAG: {str(e)}", exc_info=True)
            raise

    def _get_loader(self, file_path):
        """Retourne le loader LangChain approprié en fonction de l'extension du fichier."""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        if ext == ".pdf":
            return PyPDFLoader(file_path)
        elif ext == ".md" or ext == ".txt":
            return TextLoader(file_path, encoding='utf-8') # Spécifier l'encodage
        elif ext == ".docx":
            return Docx2txtLoader(file_path)
        else:
            logger.warning(f"Extension de fichier non supportée: {ext} pour le fichier {file_path}")
            return None

    def process_document(self, file_path: str, document_id: str = None, metadata: dict = None):
        """
        Charge, découpe et indexe un document dans ChromaDB.
        
        Args:
            file_path (str): Chemin absolu vers le fichier à traiter.
            document_id (str, optional): ID unique pour le document. Généré si non fourni.
            metadata (dict, optional): Métadonnées supplémentaires à associer aux chunks.
        """
        if not os.path.exists(file_path):
            logger.error(f"Le fichier n'existe pas: {file_path}")
            return
            
        doc_id = document_id or str(uuid.uuid4())
        base_metadata = metadata or {}
        base_metadata.update({
            "document_id": doc_id,
            "source": os.path.basename(file_path),
            "source_type": "document"  # Distinguer des documents de code
        })

        logger.info(f"Traitement du document: {file_path} (ID: {doc_id})")
        try:
            loader = self._get_loader(file_path)
            if not loader:
                return

            documents = loader.load()
            if not documents:
                logger.warning(f"Aucun contenu chargé depuis: {file_path}")
                return
                
            texts = self.text_splitter.split_documents(documents)
            if not texts:
                logger.warning(f"Aucun texte extrait après découpage pour: {file_path}")
                return

            # Préparation des IDs et métadonnées pour ChromaDB
            ids = [str(uuid.uuid4()) for _ in texts]
            final_metadata = []
            for i, text in enumerate(texts):
                chunk_metadata = base_metadata.copy()
                # Fusionner les métadonnées existantes du chunk (ex: page number de PyPDFLoader)
                chunk_metadata.update(text.metadata)
                chunk_metadata["chunk_index"] = i # Ajouter l'index du chunk
                final_metadata.append(chunk_metadata)

            # Indexation dans ChromaDB
            self.vector_store.add_documents(texts, ids=ids, metadatas=final_metadata)
            logger.info(f"Document {doc_id} ({len(texts)} chunks) indexé avec succès dans la collection '{COLLECTION_NAME}'.")
            
            # Optionnel: Supprimer le fichier source après traitement réussi
            # try:
            #     os.remove(file_path)
            #     logger.info(f"Fichier source supprimé: {file_path}")
            # except OSError as e:
            #     logger.error(f"Impossible de supprimer le fichier source {file_path}: {e}")

        except Exception as e:
            logger.error(f"Erreur lors du traitement du document {doc_id} ({file_path}): {str(e)}", exc_info=True)

    def process_github_repo(self, repo_url: str, branch: str = "main", project_id: str = None):
        """
        Clone, parse et indexe le code d'un dépôt GitHub.
        
        Args:
            repo_url (str): URL du dépôt GitHub à traiter
            branch (str): Branche à cloner (par défaut: main)
            project_id (str, optional): ID unique pour le projet. Généré si non fourni.
        
        Returns:
            int: Nombre de documents indexés
        """
        project_id = project_id or str(uuid.uuid4())
        logger.info(f"Traitement du dépôt GitHub: {repo_url} (Branche: {branch}, ID: {project_id})")
        
        try:
            # Utiliser le module d'ingestion GitHub pour traiter le dépôt
            documents = self.github_ingestion.process_repository(repo_url, branch)
            
            if not documents:
                logger.warning(f"Aucun document extrait du dépôt: {repo_url}")
                return 0
            
            # Ajouter des métadonnées supplémentaires
            for doc in documents:
                doc.metadata["project_id"] = project_id
            
            # Préparation des IDs pour ChromaDB
            ids = [str(uuid.uuid4()) for _ in documents]
            
            # Indexation dans ChromaDB
            self.vector_store.add_documents(documents, ids=ids)
            logger.info(f"Dépôt GitHub {project_id} ({len(documents)} documents) indexé avec succès.")
            
            return len(documents)
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du dépôt GitHub {repo_url}: {str(e)}", exc_info=True)
            raise

    def query(self, query_text: str, filter_metadata: Dict[str, Any] = None) -> dict:
        """
        Répond à une question en utilisant les documents indexés.
        
        Args:
            query_text (str): La question de l'utilisateur.
            filter_metadata (Dict[str, Any], optional): Filtres de métadonnées pour la recherche.
                Ex: {"source_type": "code"} pour ne chercher que dans le code.
            
        Returns:
            dict: Un dictionnaire contenant la réponse et les documents sources.
                  Ex: {'answer': '...', 'source_documents': [...]}
        """
        logger.info(f"Réception de la requête: '{query_text}'")
        if not query_text:
            return {"answer": "Veuillez fournir une question.", "source_documents": []}
            
        try:
            # Configurer le retriever avec les filtres si spécifiés
            search_kwargs = {"k": 3}  # Nombre de documents à récupérer
            if filter_metadata:
                search_kwargs["filter"] = filter_metadata
            
            retriever = self.vector_store.as_retriever(search_kwargs=search_kwargs)
            
            # Mettre à jour la chaîne QA avec le nouveau retriever
            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True
            )
            
            # Exécuter la chaîne RetrievalQA
            result = qa_chain.invoke({"query": query_text})
            
            answer = result.get("result", "Aucune réponse générée.")
            source_docs = result.get("source_documents", [])
            
            # Formattage des documents sources pour la réponse
            formatted_sources = []
            for doc in source_docs:
                source_info = {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
                
                # Ajouter des informations spécifiques au type de source
                if doc.metadata.get("source_type") == "code":
                    # Pour les sources de code, ajouter un lien GitHub si disponible
                    github_link = doc.metadata.get("github_link")
                    if github_link and doc.metadata.get("repo_url"):
                        repo_url = doc.metadata.get("repo_url")
                        # Convertir l'URL du dépôt en URL de fichier GitHub
                        if repo_url.endswith(".git"):
                            repo_url = repo_url[:-4]
                        if "github.com" in repo_url:
                            branch = doc.metadata.get("branch", "main")
                            source_info["github_url"] = f"{repo_url}/blob/{branch}/{github_link}"
                
                formatted_sources.append(source_info)
            
            logger.info(f"Réponse générée pour la requête: '{query_text}'")
            return {"answer": answer, "source_documents": formatted_sources}
        
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la chaîne QA pour la requête '{query_text}': {str(e)}", exc_info=True)
            return {"answer": "Désolé, une erreur est survenue lors de la génération de la réponse.", "source_documents": []}

# Exemple d'utilisation (peut être exécuté séparément pour tester)
if __name__ == '__main__':
    # Assurez-vous que ChromaDB est accessible (ex: lancé via docker-compose)
    # Définir la clé API OpenAI si nécessaire pour tester avec les vrais modèles
    # os.environ["OPENAI_API_KEY"] = "votre_cle_api_ici"
    
    pipeline = RAGPipeline()
    
    # Créer des fichiers de test
    TEST_DIR = "/home/ubuntu/docai/test_docs"
    os.makedirs(TEST_DIR, exist_ok=True)
    test_md_path = os.path.join(TEST_DIR, "test_doc.md")
    test_pdf_path = os.path.join(TEST_DIR, "test_doc.pdf") # Nécessite un vrai PDF

    with open(test_md_path, "w", encoding='utf-8') as f:
        f.write("# Document de Test\n\nCeci est un exemple de document Markdown pour DocAI.\nIl contient des informations sur l'IA et le RAG.\nLangChain est un framework utile.")
    
    # --- Création d'un PDF simple (nécessite reportlab) --- 
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        c = canvas.Canvas(test_pdf_path, pagesize=letter)
        c.drawString(100, 750, "Document PDF de Test")
        c.drawString(100, 735, "Ce PDF contient des informations sur les systèmes RAG.")
        c.drawString(100, 720, "ChromaDB stocke les embeddings.")
        c.save()
        logger.info(f"Fichier PDF de test créé: {test_pdf_path}")
        # Traiter le PDF
        pipeline.process_document(test_pdf_path, metadata={"type": "pdf_test"})
    except ImportError:
        logger.warning("reportlab non installé. Impossible de créer un PDF de test. Ignorez le traitement PDF.")
    except Exception as e:
        logger.error(f"Erreur lors de la création ou du traitement du PDF de test: {e}")
    # --- Fin création PDF --- 

    # Traiter le document Markdown
    pipeline.process_document(test_md_path, metadata={"type": "markdown_test"})
    
    # Tester l'ingestion de code GitHub (avec un petit dépôt public)
    try:
        test_repo = "https://github.com/langchain-ai/langchain-examples.git"
        logger.info(f"Test d'ingestion du dépôt GitHub: {test_repo}")
        num_docs = pipeline.process_github_repo(test_repo, branch="main")
        logger.info(f"Ingestion GitHub terminée: {num_docs} documents indexés")
    except Exception as e:
        logger.error(f"Erreur lors du test d'ingestion GitHub: {e}")
    
    # Attendre un peu pour l'indexation (peut être nécessaire selon la configuration de Chroma)
    time.sleep(2)

    # Poser une question sur les documents
    query = "Qu'est-ce que LangChain?"
    response = pipeline.query(query)
    print(f"\nRequête: {query}")
    print(f"Réponse: {response['answer']}")
    print("Sources:")
    for source in response['source_documents']:
        source_type = source['metadata'].get('source_type', 'inconnu')
        if source_type == 'code':
            print(f"  - Code: {source['metadata'].get('relative_path', 'inconnu')} (lignes {source['metadata'].get('start_line', '?')}-{source['metadata'].get('end_line', '?')})")
            if 'github_url' in source:
                print(f"    URL GitHub: {source['github_url']}")
        else:
            print(f"  - Document: {source['metadata'].get('source', 'inconnu')}")
        # print(f"    Extrait: {source['content'][:100]}...") # Décommenter pour voir l'extrait

    # Poser une question spécifique au code
    query2 = "Comment fonctionne le parsing de code dans LangChain?"
    response2 = pipeline.query(query2, filter_metadata={"source_type": "code"})
    print(f"\nRequête (code uniquement): {query2}")
    print(f"Réponse: {response2['answer']}")
    print("Sources de code:")
    for source in response2['source_documents']:
        print(f"  - Fichier: {source['metadata'].get('relative_path', 'inconnu')}")
        print(f"    Lignes: {source['metadata'].get('start_line', '?')}-{source['metadata'].get('end_line', '?')}")
        if 'github_url' in source:
            print(f"    URL GitHub: {source['github_url']}")
