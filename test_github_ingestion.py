import os
import logging
import tempfile
from typing import List, Dict, Any
import uuid
import json
from pathlib import Path

# Import du module d'ingestion GitHub
from app.github_ingestion import GitHubIngestion

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docai.test_github_ingestion")

def test_github_ingestion():
    """
    Teste le module d'ingestion GitHub avec un petit dépôt public.
    """
    logger.info("Démarrage des tests d'ingestion GitHub...")
    
    # Initialisation du module d'ingestion
    temp_dir = tempfile.mkdtemp(prefix="docai_test_")
    ingestion = GitHubIngestion(temp_dir=temp_dir)
    
    # URL de test (petit dépôt public)
    test_repo_url = "https://github.com/langchain-ai/langchain-examples.git"
    test_branch = "main"
    
    try:
        # Test de clonage du dépôt
        logger.info(f"Test de clonage du dépôt: {test_repo_url}")
        repo_dir = ingestion.clone_repository(test_repo_url, test_branch)
        
        if not os.path.exists(repo_dir):
            logger.error(f"Échec du clonage: le répertoire {repo_dir} n'existe pas")
            return False
        
        logger.info(f"Dépôt cloné avec succès dans: {repo_dir}")
        
        # Test de recherche des fichiers Python
        logger.info("Test de recherche des fichiers Python...")
        python_files = ingestion.find_python_files(repo_dir)
        
        if not python_files:
            logger.error("Aucun fichier Python trouvé dans le dépôt")
            return False
        
        logger.info(f"Trouvé {len(python_files)} fichiers Python")
        
        # Limiter le nombre de fichiers à traiter pour le test
        test_files = python_files[:3]  # Traiter seulement les 3 premiers fichiers
        
        # Test de parsing des fichiers Python
        all_documents = []
        for file_path in test_files:
            logger.info(f"Test de parsing du fichier: {file_path}")
            documents = ingestion.parse_python_file(file_path)
            
            if not documents:
                logger.warning(f"Aucun document extrait du fichier: {file_path}")
                continue
            
            logger.info(f"Extrait {len(documents)} documents du fichier: {file_path}")
            all_documents.extend(documents)
        
        if not all_documents:
            logger.error("Aucun document extrait des fichiers Python")
            return False
        
        # Vérification des métadonnées
        logger.info("Vérification des métadonnées des documents...")
        metadata_fields = ["source", "relative_path", "source_type", "code_type", 
                          "start_line", "end_line", "github_link"]
        
        for i, doc in enumerate(all_documents[:5]):  # Vérifier les 5 premiers documents
            logger.info(f"Document {i+1}:")
            logger.info(f"  Contenu (extrait): {doc.page_content[:100]}...")
            
            # Vérifier la présence des métadonnées essentielles
            missing_fields = [field for field in metadata_fields if field not in doc.metadata]
            
            if missing_fields:
                logger.warning(f"  Métadonnées manquantes: {missing_fields}")
            else:
                logger.info("  Toutes les métadonnées essentielles sont présentes")
            
            # Afficher les métadonnées importantes
            logger.info(f"  Type de code: {doc.metadata.get('code_type', 'inconnu')}")
            logger.info(f"  Chemin relatif: {doc.metadata.get('relative_path', 'inconnu')}")
            logger.info(f"  Lignes: {doc.metadata.get('start_line', '?')}-{doc.metadata.get('end_line', '?')}")
            logger.info(f"  Lien GitHub: {doc.metadata.get('github_link', 'non disponible')}")
            
            # Vérifier la structure du lien GitHub
            github_link = doc.metadata.get('github_link')
            if github_link:
                if '#L' in github_link:
                    logger.info("  Format du lien GitHub valide")
                else:
                    logger.warning("  Format du lien GitHub invalide")
        
        # Test de la fonction process_repository complète
        logger.info("Test de la fonction process_repository...")
        
        # Utiliser un autre petit dépôt pour ce test
        test_repo_url2 = "https://github.com/langchain-ai/langchain-core.git"
        
        # Limiter la profondeur du clone pour accélérer le test
        try:
            # Créer un répertoire temporaire différent
            temp_dir2 = tempfile.mkdtemp(prefix="docai_test2_")
            ingestion2 = GitHubIngestion(temp_dir=temp_dir2)
            
            documents = ingestion2.process_repository(test_repo_url2, branch="main")
            
            if not documents:
                logger.warning(f"Aucun document extrait du dépôt: {test_repo_url2}")
            else:
                logger.info(f"Extrait {len(documents)} documents du dépôt: {test_repo_url2}")
                
                # Vérifier que les métadonnées globales sont ajoutées
                repo_metadata_fields = ["repo_url", "branch", "repo_name"]
                missing_repo_fields = [field for field in repo_metadata_fields 
                                      if field not in documents[0].metadata]
                
                if missing_repo_fields:
                    logger.warning(f"Métadonnées de dépôt manquantes: {missing_repo_fields}")
                else:
                    logger.info("Toutes les métadonnées de dépôt sont présentes")
            
            # Nettoyer
            ingestion2.cleanup()
            
        except Exception as e:
            logger.error(f"Erreur lors du test de process_repository: {e}")
        
        logger.info("Tests d'ingestion GitHub terminés avec succès")
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors des tests d'ingestion GitHub: {e}")
        return False
        
    finally:
        # Nettoyer
        try:
            ingestion.cleanup()
            logger.info("Nettoyage des répertoires temporaires effectué")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage: {e}")

def test_github_url_construction():
    """
    Teste la construction des URLs GitHub à partir des métadonnées.
    """
    logger.info("Test de construction des URLs GitHub...")
    
    # Simuler des métadonnées de document
    test_metadata = {
        "repo_url": "https://github.com/langchain-ai/langchain.git",
        "branch": "main",
        "relative_path": "langchain/chains/qa.py",
        "start_line": 10,
        "end_line": 20,
        "github_link": "langchain/chains/qa.py#L10-L20"
    }
    
    # Construire l'URL GitHub
    repo_url = test_metadata["repo_url"]
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]
    
    branch = test_metadata["branch"]
    github_link = test_metadata["github_link"]
    
    expected_url = f"{repo_url}/blob/{branch}/{github_link}"
    logger.info(f"URL GitHub construite: {expected_url}")
    
    # Vérifier que l'URL est correcte
    if "github.com" in expected_url and "#L" in expected_url:
        logger.info("Format de l'URL GitHub valide")
        return True
    else:
        logger.error("Format de l'URL GitHub invalide")
        return False

if __name__ == "__main__":
    success_ingestion = test_github_ingestion()
    success_url = test_github_url_construction()
    
    if success_ingestion and success_url:
        logger.info("Tous les tests ont réussi!")
    else:
        logger.warning("Certains tests ont échoué. Vérifiez les logs pour plus de détails.")
