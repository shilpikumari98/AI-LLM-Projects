
# PostgreSQL Settings Vector Embeddings & AI Insights Search

This project provides a dynamic, AI-enhanced search interface to explore PostgreSQL configuration settings and related AI-generated insights. It combines vector embeddings, fuzzy search, and a large language model (LLM) to deliver rich, context-aware answers tailored to user queries about PostgreSQL settings.

---

## 🚀 Features

- **FastAPI backend**: Serves REST APIs to interact with PostgreSQL metadata and insights.
- **PostgreSQL integration**: Stores settings metadata and AI insights with vector embeddings for similarity search.
- **Vector embeddings**: Uses SentenceTransformers to embed settings and AI insights for semantic search.
- **Hybrid search**: Combines exact matching, fuzzy matching, BM25 ranking, and vector similarity.
- **OpenAI/SambaNova LLM integration**: Queries a powerful large language model (Llama 4) for Google-like, real-time AI answers, with fallback to local vector search.
- **Frontend interface**: Simple and responsive UI to query settings and view detailed insights.
- **Robust testing**: Automated pytest tests cover API endpoints and the hybrid LLM/fallback logic.

---

## 🛠 Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL with `pgvector` extension installed and enabled
- Access to OpenAI/SambaNova API credentials

### Installation

1. **Clone the repository**:

   ```bash
   git clone https://your-repo-url.git
   cd pg-settings-ve
   ```

2. **Create and activate a virtual environment**:

   ```bash
   python -m venv myenv
   source myenv/bin/activate  # Linux/macOS
   myenv\Scripts\activate     # Windows
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Download spaCy English model**:

   ```bash
   python -m spacy download en_core_web_sm
   ```

5. **Configure PostgreSQL connection** in `backend/app/database.py`.

6. **Set OpenAI/SambaNova API credentials** in `backend/app/llm_api.py` or as environment variables.

---

## ▶ Usage

### Run the backend server

```bash
uvicorn backend.app.main:app --reload
```

### Open the frontend

* Open `frontend/index.html` in a browser
  *(or configure the backend to serve it).*

### Search for settings

Enter queries about PostgreSQL settings (e.g., **"What does max\_connections do?"**) and get responses powered by:

* **LLM real-time answers** (OpenAI/SambaNova powered)
* **Fallback to vector embedding and metadata search**

---

## 📂 Project Structure

```
pg-settings-ve/
├── backend/
│   └── app/
│       ├── database.py           # DB connection and setup
│       ├── main.py               # FastAPI app and route registration
│       ├── models.py             # SQLAlchemy ORM models
│       ├── schemas.py            # Pydantic models
│       ├── crud.py               # DB CRUD operations
│       ├── search.py             # Search API with hybrid LLM/fallback logic
│       ├── llm_api.py            # LLM API integration (OpenAI/SambaNova)
│       ├── test_backend.py       # API and integration tests
├── frontend/
│   ├── index.html                # Frontend UI
│   ├── app.js                    # Frontend logic
│   ├── styles.css                # Styling
├── sql/
│   └── create_tables.sql         # DB schema and extensions
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## 🧪 Testing

Run tests with:

```bash
python -m pytest backend/app/test_backend.py
```

Tests cover:

* Database connectivity and CRUD endpoints
* Insight retrieval and recommendations
* `/search` endpoint with mocked LLM success and fallback scenarios

---

## ⚡ Notes

* Ensure your PostgreSQL server has the **`pgvector` extension** installed and enabled.
* Your **OpenAI/SambaNova API key** must be valid and have correct model permissions.
* The **hybrid search prioritizes LLM answers** for real-time, Google-like responses, falling back to precise vector searches if LLM fails.
* Adjust connection strings and API keys in config files as appropriate for your environment.

---

## 🙌 Acknowledgments

* [FastAPI](https://fastapi.tiangolo.com/)
* [Sentence Transformers](https://www.sbert.net/)
* [pgvector for PostgreSQL](https://github.com/pgvector/pgvector)
* [SpaCy](https://spacy.io/)
* [OpenAI & SambaNova LLM](https://sambanova.ai/)

```
