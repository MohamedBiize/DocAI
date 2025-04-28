import os
import logging
import tempfile
import shutil
import ast
import re
from typing import List, Dict, Any, Tuple, Optional
import uuid
from pathlib import Path
import subprocess
from langchain.schema import Document

# Configuration du logging
logger = logging.getLogger("docai.github_ingestion")

class GitHubIngestion:
    """
    Module responsable du clonage et du parsing des dépôts GitHub.
    Extrait les fonctions, classes, méthodes et leurs docstrings.
    """
    
    def __init__(self, temp_dir: str = None):
        """
        Initialise le module d'ingestion GitHub.
        
        Args:
            temp_dir: Répertoire temporaire pour cloner les dépôts.
                     Si None, utilise le répertoire temporaire du système.
        """
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="docai_github_")
        logger.info(f"Module d'ingestion GitHub initialisé avec répertoire temporaire: {self.temp_dir}")
    
    def clone_repository(self, repo_url: str, branch: str = "main") -> str:
        """
        Clone un dépôt GitHub dans un répertoire temporaire.
        
        Args:
            repo_url: URL du dépôt GitHub à cloner
            branch: Branche à cloner (par défaut: main)
            
        Returns:
            Chemin vers le répertoire cloné
            
        Raises:
            Exception: Si le clonage échoue
        """
        # Extraire le nom du dépôt depuis l'URL
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        clone_dir = os.path.join(self.temp_dir, repo_name)
        
        # Supprimer le répertoire s'il existe déjà
        if os.path.exists(clone_dir):
            shutil.rmtree(clone_dir)
        
        logger.info(f"Clonage du dépôt {repo_url} (branche: {branch}) vers {clone_dir}")
        
        try:
            # Utilisation de subprocess pour cloner le dépôt
            cmd = ["git", "clone", "--branch", branch, "--single-branch", repo_url, clone_dir]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Dépôt cloné avec succès: {clone_dir}")
            return clone_dir
        except subprocess.CalledProcessError as e:
            error_msg = f"Erreur lors du clonage du dépôt {repo_url}: {e.stderr}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def find_python_files(self, repo_dir: str) -> List[str]:
        """
        Trouve tous les fichiers Python dans le dépôt cloné.
        
        Args:
            repo_dir: Chemin vers le répertoire du dépôt cloné
            
        Returns:
            Liste des chemins vers les fichiers Python
        """
        python_files = []
        
        for root, _, files in os.walk(repo_dir):
            for file in files:
                if file.endswith(".py"):
                    python_files.append(os.path.join(root, file))
        
        logger.info(f"Trouvé {len(python_files)} fichiers Python dans {repo_dir}")
        return python_files
    
    def parse_python_file(self, file_path: str) -> List[Document]:
        """
        Parse un fichier Python pour extraire les fonctions, classes et leurs docstrings.
        
        Args:
            file_path: Chemin vers le fichier Python à parser
            
        Returns:
            Liste de documents LangChain contenant le code extrait avec métadonnées
        """
        logger.info(f"Parsing du fichier Python: {file_path}")
        documents = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Obtenir le chemin relatif pour les métadonnées
            repo_dir = os.path.dirname(os.path.dirname(file_path))
            relative_path = os.path.relpath(file_path, repo_dir)
            
            # Parser le code avec ast
            try:
                tree = ast.parse(content)
                
                # Extraire les fonctions et méthodes
                for node in ast.walk(tree):
                    # Traitement des fonctions
                    if isinstance(node, ast.FunctionDef):
                        doc = self._extract_function(node, content, file_path, relative_path)
                        if doc:
                            documents.append(doc)
                    
                    # Traitement des classes
                    elif isinstance(node, ast.ClassDef):
                        # Document pour la classe elle-même
                        class_doc = self._extract_class(node, content, file_path, relative_path)
                        if class_doc:
                            documents.append(class_doc)
                        
                        # Documents pour les méthodes de la classe
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                method_doc = self._extract_method(item, node.name, content, file_path, relative_path)
                                if method_doc:
                                    documents.append(method_doc)
                
                logger.info(f"Extrait {len(documents)} éléments de code depuis {file_path}")
                
            except SyntaxError as e:
                logger.warning(f"Erreur de syntaxe lors du parsing de {file_path}: {e}")
                # Fallback: traiter le fichier comme un document texte simple
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": file_path,
                        "relative_path": relative_path,
                        "source_type": "code",
                        "code_type": "python_file",
                        "parsing_error": str(e)
                    }
                )
                documents.append(doc)
        
        except Exception as e:
            logger.error(f"Erreur lors du parsing du fichier {file_path}: {e}")
        
        return documents
    
    def _get_line_numbers(self, node: ast.AST) -> Tuple[int, int]:
        """
        Obtient les numéros de ligne de début et de fin d'un nœud AST.
        
        Args:
            node: Nœud AST
            
        Returns:
            Tuple (ligne_début, ligne_fin)
        """
        start_line = getattr(node, 'lineno', 0)
        end_line = getattr(node, 'end_lineno', start_line)
        if not end_line:  # Pour les versions d'ast qui ne supportent pas end_lineno
            end_line = start_line
        return start_line, end_line
    
    def _extract_source_code(self, node: ast.AST, content: str) -> str:
        """
        Extrait le code source d'un nœud AST.
        
        Args:
            node: Nœud AST
            content: Contenu complet du fichier
            
        Returns:
            Code source extrait
        """
        start_line, end_line = self._get_line_numbers(node)
        lines = content.splitlines()
        
        # Ajuster les indices pour l'accès à la liste (0-based)
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        
        return "\n".join(lines[start_idx:end_idx])
    
    def _extract_docstring(self, node: ast.AST) -> Optional[str]:
        """
        Extrait la docstring d'un nœud AST.
        
        Args:
            node: Nœud AST (fonction ou classe)
            
        Returns:
            Docstring extraite ou None si absente
        """
        docstring = ast.get_docstring(node)
        return docstring.strip() if docstring else None
    
    def _extract_function(self, node: ast.FunctionDef, content: str, file_path: str, relative_path: str) -> Optional[Document]:
        """
        Extrait les informations d'une fonction.
        
        Args:
            node: Nœud AST de la fonction
            content: Contenu complet du fichier
            file_path: Chemin absolu du fichier
            relative_path: Chemin relatif du fichier
            
        Returns:
            Document LangChain contenant les informations de la fonction
        """
        start_line, end_line = self._get_line_numbers(node)
        source_code = self._extract_source_code(node, content)
        docstring = self._extract_docstring(node)
        
        # Construire la signature de la fonction
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        
        signature = f"def {node.name}({', '.join(args)})"
        
        # Construire le contenu du document
        page_content = f"Function: {node.name}\n\n"
        page_content += f"Signature: {signature}\n\n"
        
        if docstring:
            page_content += f"Docstring:\n{docstring}\n\n"
        
        page_content += f"Source Code:\n{source_code}"
        
        # Créer le document avec métadonnées
        return Document(
            page_content=page_content,
            metadata={
                "source": file_path,
                "relative_path": relative_path,
                "source_type": "code",
                "code_type": "function",
                "function_name": node.name,
                "start_line": start_line,
                "end_line": end_line,
                "has_docstring": docstring is not None,
                "github_link": f"{relative_path}#L{start_line}-L{end_line}"
            }
        )
    
    def _extract_class(self, node: ast.ClassDef, content: str, file_path: str, relative_path: str) -> Optional[Document]:
        """
        Extrait les informations d'une classe.
        
        Args:
            node: Nœud AST de la classe
            content: Contenu complet du fichier
            file_path: Chemin absolu du fichier
            relative_path: Chemin relatif du fichier
            
        Returns:
            Document LangChain contenant les informations de la classe
        """
        start_line, end_line = self._get_line_numbers(node)
        source_code = self._extract_source_code(node, content)
        docstring = self._extract_docstring(node)
        
        # Construire la liste des bases (héritage)
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(f"{base.value.id}.{base.attr}")
        
        # Construire le contenu du document
        page_content = f"Class: {node.name}\n\n"
        
        if bases:
            page_content += f"Inherits from: {', '.join(bases)}\n\n"
        
        if docstring:
            page_content += f"Docstring:\n{docstring}\n\n"
        
        # Extraire les attributs de classe (variables de classe)
        class_attrs = []
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_attrs.append(target.id)
        
        if class_attrs:
            page_content += f"Class attributes: {', '.join(class_attrs)}\n\n"
        
        # Extraire les noms des méthodes
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)
        
        if methods:
            page_content += f"Methods: {', '.join(methods)}\n\n"
        
        page_content += f"Source Code:\n{source_code}"
        
        # Créer le document avec métadonnées
        return Document(
            page_content=page_content,
            metadata={
                "source": file_path,
                "relative_path": relative_path,
                "source_type": "code",
                "code_type": "class",
                "class_name": node.name,
                "start_line": start_line,
                "end_line": end_line,
                "has_docstring": docstring is not None,
                "methods": methods,
                "github_link": f"{relative_path}#L{start_line}-L{end_line}"
            }
        )
    
    def _extract_method(self, node: ast.FunctionDef, class_name: str, content: str, file_path: str, relative_path: str) -> Optional[Document]:
        """
        Extrait les informations d'une méthode de classe.
        
        Args:
            node: Nœud AST de la méthode
            class_name: Nom de la classe parente
            content: Contenu complet du fichier
            file_path: Chemin absolu du fichier
            relative_path: Chemin relatif du fichier
            
        Returns:
            Document LangChain contenant les informations de la méthode
        """
        start_line, end_line = self._get_line_numbers(node)
        source_code = self._extract_source_code(node, content)
        docstring = self._extract_docstring(node)
        
        # Construire la signature de la méthode
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        
        signature = f"def {node.name}({', '.join(args)})"
        
        # Déterminer le type de méthode
        method_type = "instance_method"
        if args and args[0] == "self":
            method_type = "instance_method"
        elif args and args[0] == "cls":
            method_type = "class_method"
        elif node.decorator_list:
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    if decorator.id == "staticmethod":
                        method_type = "static_method"
                    elif decorator.id == "classmethod":
                        method_type = "class_method"
                    elif decorator.id == "property":
                        method_type = "property"
        
        # Construire le contenu du document
        page_content = f"Method: {class_name}.{node.name}\n\n"
        page_content += f"Type: {method_type}\n\n"
        page_content += f"Signature: {signature}\n\n"
        
        if docstring:
            page_content += f"Docstring:\n{docstring}\n\n"
        
        page_content += f"Source Code:\n{source_code}"
        
        # Créer le document avec métadonnées
        return Document(
            page_content=page_content,
            metadata={
                "source": file_path,
                "relative_path": relative_path,
                "source_type": "code",
                "code_type": "method",
                "method_name": node.name,
                "class_name": class_name,
                "method_type": method_type,
                "start_line": start_line,
                "end_line": end_line,
                "has_docstring": docstring is not None,
                "github_link": f"{relative_path}#L{start_line}-L{end_line}"
            }
        )
    
    def process_repository(self, repo_url: str, branch: str = "main") -> List[Document]:
        """
        Traite un dépôt GitHub complet: clone, parse et extrait les documents.
        
        Args:
            repo_url: URL du dépôt GitHub
            branch: Branche à cloner (par défaut: main)
            
        Returns:
            Liste de documents LangChain contenant le code extrait avec métadonnées
        """
        all_documents = []
        repo_dir = None
        
        try:
            # Cloner le dépôt
            repo_dir = self.clone_repository(repo_url, branch)
            
            # Trouver tous les fichiers Python
            python_files = self.find_python_files(repo_dir)
            
            # Parser chaque fichier Python
            for file_path in python_files:
                documents = self.parse_python_file(file_path)
                all_documents.extend(documents)
            
            # Ajouter des métadonnées globales à tous les documents
            for doc in all_documents:
                doc.metadata["repo_url"] = repo_url
                doc.metadata["branch"] = branch
                doc.metadata["repo_name"] = repo_url.split("/")[-1].replace(".git", "")
            
            logger.info(f"Traitement terminé pour {repo_url}: {len(all_documents)} documents extraits")
            
            return all_documents
        
        except Exception as e:
            logger.error(f"Erreur lors du traitement du dépôt {repo_url}: {e}")
            raise
        
        finally:
            # Nettoyer le répertoire cloné si demandé
            # Note: on peut choisir de le conserver pour des traitements ultérieurs
            # if repo_dir and os.path.exists(repo_dir):
            #     shutil.rmtree(repo_dir)
            #     logger.info(f"Répertoire temporaire nettoyé: {repo_dir}")
            pass
    
    def cleanup(self):
        """
        Nettoie les répertoires temporaires créés par le module.
        """
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Répertoire temporaire nettoyé: {self.temp_dir}")

# Exemple d'utilisation
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # URL de test (dépôt public)
    test_repo_url = "https://github.com/langchain-ai/langchain.git"
    
    # Initialiser le module d'ingestion
    ingestion = GitHubIngestion()
    
    try:
        # Traiter le dépôt
        documents = ingestion.process_repository(test_repo_url, branch="main")
        
        # Afficher quelques statistiques
        print(f"Nombre total de documents extraits: {len(documents)}")
        
        # Compter les types de documents
        code_types = {}
        for doc in documents:
            code_type = doc.metadata.get("code_type", "unknown")
            code_types[code_type] = code_types.get(code_type, 0) + 1
        
        print("Répartition par type:")
        for code_type, count in code_types.items():
            print(f"  - {code_type}: {count}")
        
        # Afficher quelques exemples
        if documents:
            print("\nExemple de document:")
            print(f"Contenu: {documents[0].page_content[:200]}...")
            print(f"Métadonnées: {documents[0].metadata}")
    
    finally:
        # Nettoyer
        ingestion.cleanup()
