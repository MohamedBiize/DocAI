import os
import logging
from typing import List, Dict, Any
import uuid

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docai.test_rag")

# Import du pipeline RAG
from app.rag_pipeline import RAGPipeline

def create_test_documents(test_dir: str) -> List[str]:
    """
    Crée des documents de test pour évaluer le pipeline RAG.
    
    Args:
        test_dir: Répertoire où créer les documents de test
        
    Returns:
        Liste des chemins des fichiers créés
    """
    os.makedirs(test_dir, exist_ok=True)
    created_files = []
    
    # Création d'un document Markdown
    md_path = os.path.join(test_dir, "test_medical_terms.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("""# Termes médicaux courants

## Cardiologie
- **Infarctus du myocarde**: Nécrose d'une partie du muscle cardiaque suite à une obstruction d'une artère coronaire.
- **Fibrillation auriculaire**: Trouble du rythme cardiaque caractérisé par des contractions rapides et irrégulières des oreillettes.
- **Insuffisance cardiaque**: Incapacité du cœur à pomper suffisamment de sang pour répondre aux besoins de l'organisme.

## Pneumologie
- **BPCO**: Bronchopneumopathie chronique obstructive, maladie pulmonaire caractérisée par une obstruction progressive des voies aériennes.
- **Asthme**: Maladie inflammatoire chronique des voies respiratoires caractérisée par une hyperréactivité bronchique.
- **Pneumonie**: Infection aiguë du parenchyme pulmonaire, généralement d'origine bactérienne ou virale.

## Neurologie
- **AVC**: Accident vasculaire cérébral, interruption soudaine de la circulation sanguine dans le cerveau.
- **Maladie de Parkinson**: Maladie neurodégénérative affectant le système nerveux central.
- **Épilepsie**: Trouble neurologique caractérisé par des crises récurrentes dues à une activité électrique anormale dans le cerveau.
""")
    created_files.append(md_path)
    logger.info(f"Document Markdown créé: {md_path}")
    
    # Création d'un document texte
    txt_path = os.path.join(test_dir, "test_rag_system.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("""Système RAG (Retrieval-Augmented Generation)

Un système RAG combine la recherche d'information (retrieval) avec la génération de texte (generation) pour produire des réponses précises et contextuelles.

Composants principaux d'un système RAG:

1. Base de connaissances: Collection de documents indexés sous forme de vecteurs (embeddings).
2. Système de recherche: Utilise la similarité vectorielle pour trouver les documents pertinents à une requête.
3. Modèle de langage: Génère une réponse cohérente en utilisant les documents récupérés comme contexte.

Avantages des systèmes RAG:
- Réduction des hallucinations du modèle de langage
- Capacité à accéder à des informations spécifiques et à jour
- Possibilité de citer les sources d'information
- Adaptation à des domaines spécialisés sans fine-tuning complet du modèle

ChromaDB est une base de données vectorielle populaire pour stocker et rechercher des embeddings dans les systèmes RAG.
LangChain est un framework qui facilite la création de pipelines RAG en connectant différents composants.
""")
    created_files.append(txt_path)
    logger.info(f"Document texte créé: {txt_path}")
    
    # Création d'un PDF simple avec reportlab
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        from reportlab.lib.units import inch
        
        pdf_path = os.path.join(test_dir, "test_medyouin_company.pdf")
        
        doc = SimpleDocTemplate(pdf_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Titre
        story.append(Paragraph("MedYouIN - Présentation de l'entreprise", styles['Title']))
        story.append(Spacer(1, 0.25*inch))
        
        # Introduction
        story.append(Paragraph("MedYouIN est une entreprise innovante dans le secteur de la santé numérique, spécialisée dans le développement de solutions d'intelligence artificielle pour améliorer l'accès à l'information médicale et la prise de décision clinique.", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Mission
        story.append(Paragraph("Notre mission", styles['Heading2']))
        story.append(Paragraph("Démocratiser l'accès à l'information médicale de qualité et faciliter la collaboration entre professionnels de santé grâce à des outils d'IA éthiques et transparents.", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Produits
        story.append(Paragraph("Nos produits", styles['Heading2']))
        story.append(Paragraph("1. <b>DocAI</b>: Assistant virtuel basé sur une architecture RAG (Retrieval-Augmented Generation) pour l'accès rapide à la documentation interne et aux connaissances médicales.", styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("2. <b>MedConnect</b>: Plateforme collaborative permettant aux médecins de partager des cas cliniques anonymisés et d'obtenir des avis d'experts.", styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("3. <b>HealthScan</b>: Outil d'analyse de littérature médicale qui synthétise les dernières recherches sur des sujets spécifiques.", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Valeurs
        story.append(Paragraph("Nos valeurs", styles['Heading2']))
        story.append(Paragraph("- <b>Précision</b>: Nous nous engageons à fournir des informations médicales exactes et à jour.", styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("- <b>Confidentialité</b>: La protection des données de santé est au cœur de notre approche.", styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("- <b>Innovation responsable</b>: Nous développons des technologies d'IA qui augmentent les capacités humaines sans les remplacer.", styles['Normal']))
        
        doc.build(story)
        created_files.append(pdf_path)
        logger.info(f"Document PDF créé: {pdf_path}")
    except ImportError:
        logger.warning("reportlab non installé. Impossible de créer un PDF de test.")
    except Exception as e:
        logger.error(f"Erreur lors de la création du PDF: {e}")
    
    return created_files

def test_rag_pipeline():
    """
    Teste le pipeline RAG avec des documents et des requêtes.
    """
    logger.info("Démarrage des tests du pipeline RAG...")
    
    # Création du répertoire de test
    test_dir = "/home/ubuntu/docai/test_data"
    test_files = create_test_documents(test_dir)
    
    # Initialisation du pipeline RAG
    try:
        pipeline = RAGPipeline()
        logger.info("Pipeline RAG initialisé avec succès.")
    except Exception as e:
        logger.error(f"Échec de l'initialisation du pipeline RAG: {e}")
        return False
    
    # Ingestion des documents de test
    for file_path in test_files:
        try:
            doc_id = str(uuid.uuid4())
            file_name = os.path.basename(file_path)
            logger.info(f"Ingestion du document: {file_name} (ID: {doc_id})")
            
            # Déterminer le type de document basé sur l'extension
            doc_type = "unknown"
            if file_name.endswith(".md"):
                doc_type = "markdown"
            elif file_name.endswith(".txt"):
                doc_type = "text"
            elif file_name.endswith(".pdf"):
                doc_type = "pdf"
            
            # Métadonnées pour le document
            metadata = {
                "document_type": doc_type,
                "test_document": True,
                "filename": file_name
            }
            
            # Traitement du document
            pipeline.process_document(file_path, document_id=doc_id, metadata=metadata)
            logger.info(f"Document {file_name} traité avec succès.")
        except Exception as e:
            logger.error(f"Erreur lors du traitement du document {file_path}: {e}")
            return False
    
    # Attendre un peu pour l'indexation
    import time
    logger.info("Attente de 3 secondes pour l'indexation...")
    time.sleep(3)
    
    # Liste de questions de test
    test_questions = [
        "Qu'est-ce qu'un système RAG et quels sont ses composants principaux?",
        "Quels sont les symptômes de l'infarctus du myocarde?",
        "Quels produits propose l'entreprise MedYouIN?",
        "Quelle est la différence entre l'asthme et la BPCO?",
        "Comment ChromaDB est-il utilisé dans un système RAG?"
    ]
    
    # Test des questions
    results = []
    for question in test_questions:
        try:
            logger.info(f"Test de la question: '{question}'")
            response = pipeline.query(question)
            
            # Vérification de la réponse
            if not response or not response.get("answer"):
                logger.warning(f"Pas de réponse générée pour la question: '{question}'")
                results.append({
                    "question": question,
                    "success": False,
                    "error": "Pas de réponse générée"
                })
                continue
            
            # Vérification des documents sources
            if not response.get("source_documents"):
                logger.warning(f"Pas de documents sources pour la question: '{question}'")
            
            # Enregistrement du résultat
            results.append({
                "question": question,
                "success": True,
                "answer": response.get("answer"),
                "source_count": len(response.get("source_documents", []))
            })
            logger.info(f"Réponse générée avec succès pour la question: '{question}'")
        except Exception as e:
            logger.error(f"Erreur lors du test de la question '{question}': {e}")
            results.append({
                "question": question,
                "success": False,
                "error": str(e)
            })
    
    # Résumé des résultats
    success_count = sum(1 for r in results if r["success"])
    logger.info(f"Tests terminés: {success_count}/{len(results)} questions répondues avec succès.")
    
    # Affichage des résultats détaillés
    for i, result in enumerate(results):
        if result["success"]:
            logger.info(f"Question {i+1}: '{result['question']}'")
            logger.info(f"  Réponse: {result['answer'][:100]}...")
            logger.info(f"  Sources: {result['source_count']} documents")
        else:
            logger.error(f"Question {i+1}: '{result['question']}' - ÉCHEC: {result.get('error', 'Erreur inconnue')}")
    
    return success_count == len(results)

if __name__ == "__main__":
    success = test_rag_pipeline()
    if success:
        logger.info("Tous les tests du pipeline RAG ont réussi!")
    else:
        logger.warning("Certains tests du pipeline RAG ont échoué. Vérifiez les logs pour plus de détails.")
