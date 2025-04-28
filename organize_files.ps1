# Move files to their appropriate directories
Move-Item -Path "main.py" -Destination "app\core\main.py"
Move-Item -Path "rag_pipeline.py" -Destination "app\core\rag_pipeline.py"
Move-Item -Path "github.py" -Destination "app\services\github.py"
Move-Item -Path "github_ingestion.py" -Destination "app\services\github_ingestion.py"
Move-Item -Path "db_config.py" -Destination "app\core\db_config.py"

# Move test files
Move-Item -Path "test_rag.py" -Destination "tests\test_rag.py"
Move-Item -Path "test_cli.py" -Destination "tests\test_cli.py"
Move-Item -Path "test_github_ingestion.py" -Destination "tests\test_github_ingestion.py"

# Create __init__.py files
New-Item -Path "app\__init__.py" -ItemType File
New-Item -Path "app\api\__init__.py" -ItemType File
New-Item -Path "app\core\__init__.py" -ItemType File
New-Item -Path "app\models\__init__.py" -ItemType File
New-Item -Path "app\services\__init__.py" -ItemType File
New-Item -Path "app\utils\__init__.py" -ItemType File
New-Item -Path "tests\__init__.py" -ItemType File 