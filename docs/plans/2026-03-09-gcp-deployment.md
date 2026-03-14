# Google Cloud Deployment & RAG Implementation Plan

**Goal:** Deploy the MES Telegram Bot to Google Cloud Run, migrate the database to Cloud SQL (PostgreSQL), and implement the Corporate RAG system using Vertex AI for document QA.

**Architecture:** The bot will be packaged into a standard Docker container and deployed statelessly on Google Cloud Run. Data will be hosted on managed Cloud SQL. For RAG, we will use Vertex AI Embeddings and Gemini 1.5 Pro via LangChain to answer user queries using corporate documentation.

**Tech Stack:** Google Cloud Run, Cloud SQL (PostgreSQL), Docker, Vertex AI (Gemini 1.5, Embeddings), LangChain.

---

### Task 1: Authenticate and Configure Google Cloud CLI

**Step 1: Check authentication (Failing Test)**
Run: `gcloud auth list`
Expected: No active account or wrong project.

**Step 2: Authenticate and set project (Minimal Implementation)**
```bash
# USER ACTION REQUIRED: Run this in your terminal to login to your Google account
gcloud auth login

# Set the GCP project ID (replace YOUR_PROJECT_ID with your actual project ID from Console)
gcloud config set project YOUR_PROJECT_ID
```

**Step 3: Verify authentication (Passing Test)**
Run: `gcloud config get-value project`
Expected: PASS (Displays your project ID)

---

### Task 2: Enable Required Google Cloud APIs

**Step 1: Write the failing test**
Run: `gcloud services list --enabled | grep run.googleapis.com`
Expected: FAIL (empty output if not enabled)

**Step 2: Enable APIs (Minimal Implementation)**
```bash
gcloud services enable \
    run.googleapis.com \
    sqladmin.googleapis.com \
    aiplatform.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com
```

**Step 3: Verify it passes**
Run: `gcloud services list --enabled | grep run.googleapis.com`
Expected: PASS

---

### Task 3: Containerize the Application

**Files:**
- Create: `/Users/komilrasulov/Antigravity/mes_bot/Dockerfile`
- Create: `/Users/komilrasulov/Antigravity/mes_bot/.dockerignore`

**Step 1: Write minimal implementation (`Dockerfile`)**
```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (postgres drivers etc)
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Run the bot and web server
# Assuming you want to run the bot, or both via a script. For now, running bot.
CMD ["python", "-m", "bot.main"]
```

**Step 2: Write minimal implementation (`.dockerignore`)**
```text
.venv
__pycache__
.env
.git
chroma_db/
postgres_data/
```

**Step 3: Run test to verify it builds**
Run: `docker build -t mes-bot-test .`
Expected: PASS (Docker image builds successfully)

**Step 4: Commit**
```bash
git add Dockerfile .dockerignore requirements.txt
git commit -m "chore: add docker configuration for deployment"
```

---

### Task 4: Provision Cloud SQL (PostgreSQL)

**Step 1: Create Cloud SQL Instance**
```bash
gcloud sql instances create mes-postgres-db \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=europe-central2 \
    --root-password=mes_master_password
```

**Step 2: Create Application Database and User**
```bash
gcloud sql databases create mes_db --instance=mes-postgres-db
gcloud sql users create mes_user --instance=mes-postgres-db --password=mes_app_password
```

**Step 3: Verify creation**
Run: `gcloud sql instances list`
Expected: PASS (mes-postgres-db is RUNNABLE)

---

### Task 5: Deploy to Google Cloud Run

**Step 1: Submit Build to Cloud Build**
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/mes-bot
```

**Step 2: Deploy to Cloud Run**
```bash
gcloud run deploy mes-bot \
    --image gcr.io/YOUR_PROJECT_ID/mes-bot \
    --platform managed \
    --region europe-central2 \
    --allow-unauthenticated \
    --set-env-vars="DB_HOST=/cloudsql/YOUR_PROJECT_ID:europe-central2:mes-postgres-db,DB_USER=mes_user,DB_PASSWORD=mes_app_password,DB_NAME=mes_db" \
    --set-secrets="BOT_TOKEN=telegram-bot-token:latest,GEMINI_API_KEY=gemini-api-key:latest" \
    --add-cloudsql-instances="YOUR_PROJECT_ID:europe-central2:mes-postgres-db"
```

**Step 3: Verify deployment**
Check Google Cloud Console -> Cloud Run. Bot should be active and polling Telegram.

---

### Task 6: Implement RAG System using Vertex AI

*Note: The system logic for RAG will be implemented after the base bot deployment is stable and verified.*

**Files:**
- Modify: `ai_agent/ingest.py`
- Modify: `bot/handlers/ai_assistant.py`

**Actions:**
1. Replace `langchain-google-genai` with `langchain-google-vertexai`.
2. Update the embedding model to `textembedding-gecko` or `text-embedding-004` from Vertex AI.
3. Replace ChromaDB with Vertex AI Vector Search (or keep ChromaDB local inside a persistent volume if preferred for cost saving in V1).
