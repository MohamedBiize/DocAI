import requests
import argparse
import os
import json
import time

# Configuration de l'URL de base de l'API
BASE_URL = "http://localhost:8000"
UPLOAD_URL = f"{BASE_URL}/documents/upload"
ASK_URL = f"{BASE_URL}/ask"
HEALTH_URL = f"{BASE_URL}/health"

def check_api_health():
    """Vérifie si l'API est accessible."""
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
        print("API Health Check: OK")
        print(json.dumps(response.json(), indent=2))
        return True
    except requests.exceptions.RequestException as e:
        print(f"Erreur: Impossible de se connecter à l'API DocAI à {BASE_URL}.")
        print(f"Détails: {e}")
        print("Veuillez vous assurer que les conteneurs Docker sont démarrés avec 'docker-compose up --build'.")
        return False

def upload_document(file_path):
    """Télécharge un document vers l'API DocAI."""
    if not os.path.exists(file_path):
        print(f"Erreur: Le fichier '{file_path}' n'existe pas.")
        return None

    files = {'files': (os.path.basename(file_path), open(file_path, 'rb'))}
    params = {'document_type': 'cli_test'}
    
    print(f"Téléchargement du document '{file_path}' vers {UPLOAD_URL}...")
    try:
        response = requests.post(UPLOAD_URL, files=files, params=params, timeout=60)
        response.raise_for_status()
        print("Document téléchargé avec succès. Réponse de l'API:")
        print(json.dumps(response.json(), indent=2))
        # Donner un peu de temps au traitement en arrière-plan pour démarrer/indexer
        print("Attente de 5 secondes pour le début de l'indexation...")
        time.sleep(5)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors du téléchargement du document: {e}")
        if e.response is not None:
            try:
                print("Réponse de l'API (erreur):")
                print(json.dumps(e.response.json(), indent=2))
            except json.JSONDecodeError:
                print(f"Réponse de l'API (erreur non-JSON): {e.response.text}")
        return None
    finally:
        # Fermer le fichier explicitement après l'envoi
        if 'files' in locals() and 'files' in files:
             files['files'][1].close()

def ask_question(question):
    """Pose une question à l'API DocAI."""
    payload = {"question": question}
    print(f"Envoi de la question '{question}' vers {ASK_URL}...")
    try:
        response = requests.post(ASK_URL, json=payload, timeout=120) # Timeout plus long pour la génération
        response.raise_for_status()
        print("Réponse reçue de l'API:")
        result = response.json()
        print(f"  Réponse: {result.get('answer')}")
        print("  Documents sources:")
        if result.get('source_documents'):
            for i, doc in enumerate(result['source_documents']):
                print(f"    Source {i+1}:")
                print(f"      Metadata: {doc.get('metadata')}")
                # print(f"      Contenu (extrait): {doc.get('content', '')[:100]}...") # Décommenter pour voir l'extrait
        else:
            print("    Aucun document source retourné.")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la requête: {e}")
        if e.response is not None:
            try:
                print("Réponse de l'API (erreur):")
                print(json.dumps(e.response.json(), indent=2))
            except json.JSONDecodeError:
                print(f"Réponse de l'API (erreur non-JSON): {e.response.text}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Client CLI pour interagir avec l'API DocAI.")
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles", required=True)

    # Sous-commande pour vérifier la santé
    parser_health = subparsers.add_parser("health", help="Vérifie la santé de l'API DocAI.")

    # Sous-commande pour télécharger un document
    parser_upload = subparsers.add_parser("upload", help="Télécharge un document vers DocAI.")
    parser_upload.add_argument("file_path", type=str, help="Chemin vers le fichier à télécharger (PDF, MD, DOCX).")

    # Sous-commande pour poser une question
    parser_ask = subparsers.add_parser("ask", help="Pose une question à DocAI.")
    parser_ask.add_argument("question", type=str, help="La question à poser.")

    args = parser.parse_args()

    if args.command == "health":
        check_api_health()
    elif args.command == "upload":
        if check_api_health(): # Vérifier la santé avant d'uploader
            upload_document(args.file_path)
    elif args.command == "ask":
        if check_api_health(): # Vérifier la santé avant de poser une question
            ask_question(args.question)

if __name__ == "__main__":
    main()

