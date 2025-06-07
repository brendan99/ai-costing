# AI Costing Graph

A RAG (Retrieval-Augmented Generation) pipeline for generating legal costing documents using Ollama, Langchain, and Neo4j.

## Prerequisites

- Python 3.9+
- Neo4j Desktop or Docker
- Ollama installed and running

## Setup

1. Install Ollama:
   ```bash
   # For macOS
   curl https://ollama.ai/install.sh | sh
   ```

2. Pull required Ollama models:
   ```bash
   ollama pull mistral
   ollama pull nomic-embed-text
   ```

3. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Set up Neo4j:
   - Install Neo4j Desktop or run via Docker
   - Create a new database
   - Note your connection details (URI, username, password)

6. Create a `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env with your Neo4j and other configuration
   ```

## Project Structure

```
ai-costing-graph/
├── src/
│   ├── models/          # Pydantic models
│   ├── graph/           # Neo4j graph operations
│   ├── llm/             # LLM and embedding operations
│   ├── document/        # Document processing
│   └── generation/      # Document generation
├── tests/               # Test files
├── data/               # Sample data and documents
└── scripts/            # Utility scripts
```

## Usage

1. Start Ollama:
   ```bash
   ollama serve
   ```

2. Run the document ingestion pipeline:
   ```bash
   python -m src.scripts.ingest_documents
   ```

3. Generate a document:
   ```bash
   python -m src.scripts.generate_document
   ```

## Development

- Run tests: `pytest`
- Run linting: `ruff check .`
- Format code: `ruff format .`

## License

MIT 