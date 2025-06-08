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

## Latest RAG Workflow

The latest RAG workflow includes the following steps:

1. **Document Upload**:  
   Upload legal documents using the sidebar uploader. Supported formats include PDF, TXT, DOCX, and MD.

2. **Document Processing**:  
   - Documents are automatically processed and indexed.
   - Smart chunking with overlap preservation is applied.
   - Metadata extraction and preservation are performed.

3. **Vector Search**:  
   - Semantic search using BGE embeddings is utilized.
   - Results show relevant document chunks with source documents and relevance scores.

4. **Disbursement Creation**:  
   - Disbursements are created and stored in a Neo4j database.
   - A duplicate ID check is implemented to prevent errors during creation.
   - Logging is added to track the creation process and any potential issues.

5. **Resource Management**:  
   - Memory usage monitoring and automatic garbage collection are implemented.
   - Efficient storage management is ensured.

## Usage

1. Start Ollama:
   ```