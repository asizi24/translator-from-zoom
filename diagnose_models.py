import os
import vertexai
from vertexai.preview.generative_models import GenerativeModel
from google.cloud import aiplatform

# Configuration
# Assuming runs in container where env vars are set, or load from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

project_id = os.getenv("PROJECT_ID")
location = os.getenv("LOCATION", "us-central1")

print(f"Diagnostic Report")
print(f"-----------------")
print(f"Project ID: {project_id}")
print(f"Location: {location}")
print(f"Credentials: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")

if not project_id:
    print("ERROR: PROJECT_ID not set.")
    exit(1)

try:
    vertexai.init(project=project_id, location=location)
    print("Vertex AI initialized successfully.")
except Exception as e:
    print(f"ERROR: Vertex AI init failed: {e}")
    exit(1)

print("\n--- Testing Model Access ---")
models_to_test = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash", 
    "gemini-1.5-pro",
    "gemini-pro"
]

for model_name in models_to_test:
    print(f"Testing {model_name}...", end=" ")
    try:
        model = GenerativeModel(model_name)
        # Just init isn't enough, usually need to try generating or checking existence
        # But 404 often happens at generation time or split. 
        # Let's try a dry run generate
        response = model.generate_content("Hello", stream=False)
        print(f"SUCCESS (Response: {response.text.strip()})")
    except Exception as e:
        print(f"FAILED: {e}")

print("\n--- Listing All Models (if possible) ---")
try:
    # Try to list models using aiplatform
    aiplatform.init(project=project_id, location=location)
    models = aiplatform.Model.list()
    print(f"Found {len(models)} custom models (not publisher models).")
    
    # Accessing Publisher models via Model Garden API is complex, 
    # relying on the explicit test above is usually better for GenAI.
except Exception as e:
    print(f"Listing failed: {e}")

print("\nDone.")
