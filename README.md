# F1 Context Graph AI — Minimal MVP

A specialized conversational AI prototype demonstrating **Context Graph + RAG + FastF1 Telemetry Analytics** for Formula 1 data. 

Focused strictly on the **2024 Monaco Grand Prix**, comparing **Charles Leclerc (LEC, Ferrari)** and **Lando Norris (NOR, McLaren)** across **Qualifying** and **Race** sessions.

---

## 1. Architecture

```text
User
 ↓
Next.js (React Chat UI)
 ↓
FastAPI Backend (/api/chat)
 ↓
Query Orchestrator (Intent Routing)
 ├── Neo4j      → Contextual relationships (Sessions, Driver, Team, Stints, Tyres, PitStops)
 ├── PostgreSQL → Structured F1 race data & telemetry summaries
 ├── Qdrant     → Vector RAG (Race reports, FIA material, team quotes, technical analysis)
 └── Analytics  → FastF1-derived numerical computations (Pace, Sectors, Degradation)
        ↓
   Context Builder (Compiles grounded context object)
        ↓
     OpenAI LLM (gpt-4o-mini reasoning & synthesis layer)
        ↓
     Answer (Structured with evidence, sources & provenance)
```

> **Core Principle**: The LLM acts as a reasoning & synthesis layer ONLY. It is not the source of truth. Numerical facts and telemetry are computed via Python/SQL/Cypher, never invented by the LLM.

---

## 2. Role of Each Data Component

* **FastF1**: Fetches official F1 telemetry, sector times, tyre life, and weather for Monaco 2024. Processed once during ingestion and cached to avoid redundant network downloads.
* **PostgreSQL**: Stores relational structured data across 9 tables (`teams`, `drivers`, `races`, `sessions`, `laps`, `stints`, `pit_stops`, `weather`, `telemetry_summaries`).
* **Neo4j (Context Graph)**: Stores entity graph relationships (`Season -[:HAS_RACE]-> Race -[:HELD_AT]-> Circuit`, `Driver -[:DRIVES_FOR]-> Team`, `Driver -[:COMPLETED]-> Lap -[:PART_OF_STINT]-> Stint -[:USED]-> Tyre`, `Driver -[:MADE]-> PitStop`).
* **Qdrant (Vector DB)**: Stores embedded text document chunks (race reports, team quotes, technical breakdowns) with metadata filtering for RAG text retrieval.

---

## 3. Installation & Setup

### Prerequisites
1. **Python 3.11+**
2. **PostgreSQL** running locally (e.g. via pgAdmin)
3. **Docker & Docker Compose** (for Neo4j and Qdrant)
4. **Node.js 18+** (for Next.js frontend)

### Environment Configuration
Copy `.env.example` to `.env` and supply your credentials:

```bash
cp .env.example .env
```

```env
OPENAI_API_KEY=sk-...

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=f1_context
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=f1password

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

FASTF1_CACHE_DIR=./data/fastf1_cache
```

---

## 4. Running the Databases (Docker)

Start Neo4j and Qdrant using Docker Compose:

```bash
docker-compose up -d
```

Verify services:
* Neo4j Browser: `http://localhost:7474` (User: `neo4j`, Password: `f1password`)
* Qdrant Dashboard: `http://localhost:6333/dashboard`

---

## 5. Data Ingestion Pipeline

Run the sequential ingestion scripts from the `backend/` folder:

```bash
cd backend

# Step 1: Create PostgreSQL tables
python scripts/init_db.py

# Step 2: Ingest Monaco 2024 data via FastF1 into PostgreSQL
python scripts/ingest_monaco.py

# Step 3: Populate Neo4j Context Graph from PostgreSQL
python scripts/init_neo4j.py

# Step 4: Embed documents and store in Qdrant
python scripts/ingest_qdrant.py
```

---

## 6. Running the Application

### Backend (FastAPI)
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
Interactive API docs available at: `http://localhost:8000/docs`

### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## 7. Supported Demo Questions

1. Who won Monaco 2024?
2. What tyres did Norris use?
3. Compare Norris and Leclerc's race strategies.
4. Why was Leclerc faster than Norris in qualifying?
5. Where did Leclerc gain time?
6. Compare their sector performance.
7. What happened during their pit strategies?
8. What did the drivers/teams say about the race?
9. Which driver had better tyre degradation?
10. Give a data-backed comparison of Norris and Leclerc.

---

## 8. Testing

Run pytest from the `backend/` directory:

```bash
cd backend
pytest tests/ -v
```

Tests cover:
* FastF1 ingestion helper functions
* PostgreSQL models and DSN configuration
* Neo4j schema definitions
* Qdrant document chunking
* Analytics Pydantic models & calculations
* Intent classification and entity routing
* Strategy comparison integration test

---

## 9. Deployment Strategy

* **Containerization**: FastAPI backend can be containerized using a simple `Dockerfile`.
* **Databases**: Managed PostgreSQL (AWS RDS / GCP Cloud SQL), Neo4j Aura Cloud, Qdrant Cloud.
* **Frontend**: Deploy Next.js to Vercel or AWS Amplify.
* **Future Expansion**: System interfaces (`Orchestrator`, `Analytics`, `GraphQueries`, `DocumentSearch`) are abstract and modular, allowing multi-race, multi-season, or live OpenF1 streaming support to be added without breaking existing contracts.
