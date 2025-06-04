# UK Legal Costing RAG System

A Streamlit-based application that uses RAG (Retrieval-Augmented Generation) to process and analyze UK legal documents, specifically optimized for legal costing workflows, bills of costs, and solicitor-client cost assessment.

## Prerequisites

- macOS (tested on M4 MacBook Pro)
- Python 3.11+
- Docker and Docker Compose
- 48GB RAM (recommended for optimal performance)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/brendan99/ai-costing.git
cd ai-costing
```

2. Create and activate virtual environment:
```bash
python -m venv legal_rag_env
source legal_rag_env/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Start ChromaDB using Docker:
```bash
docker-compose up -d
```

## Running the Application

1. Ensure ChromaDB is running:
```bash
docker-compose ps
```

2. Run the Streamlit app:
```bash
streamlit run app.py
```

## Usage

1. Upload your legal documents using the sidebar uploader
   - Supported formats: PDF, TXT, DOCX, MD
   - Documents will be automatically processed and indexed
   - Maximum file size: 10MB per document

2. Monitor document processing
   - View real-time processing status in the sidebar
   - Check document status and chunk counts
   - Monitor system resource usage

3. Search your documents
   - Enter your query in the search box
   - Results will show relevant document chunks
   - View source documents and relevance scores

4. Manage your documents
   - View processing status for each document
   - Re-index documents if needed
   - Clear processed documents using the Reset All button

## Features

- **Document Processing**
  - Automatic text extraction from multiple formats
  - Smart chunking with overlap preservation
  - Metadata extraction and preservation
  - Progress tracking and status updates

- **Vector Search**
  - Semantic search using BGE embeddings
  - Relevance scoring and ranking
  - Source document tracking
  - Chunk-level retrieval

- **Resource Management**
  - Memory usage monitoring
  - Automatic garbage collection
  - Efficient storage management
  - Background processing

## Project Structure

```
.
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── docker-compose.yml    # ChromaDB configuration
├── uploads/              # Temporary upload directory
├── processed/            # Processed documents
├── storage/              # ChromaDB persistence
└── README.md            # This file
```

## System Requirements

- **Hardware**
  - 48GB RAM recommended
  - M4/M3/M2 MacBook Pro or equivalent
  - Sufficient disk space for document storage

- **Software**
  - Python 3.11 or higher
  - Docker and Docker Compose
  - Modern web browser

## Troubleshooting

### Common Issues

1. **ChromaDB Connection Issues**
   - Ensure Docker is running
   - Check ChromaDB container status
   - Verify port 8000 is available

2. **Memory Issues**
   - Monitor memory usage in the sidebar
   - Close other applications to free RAM
   - Use the Reset All button to clear memory

3. **Document Processing Issues**
   - Check file size limits (10MB max)
   - Verify supported file formats
   - Monitor processing status in sidebar

4. **Search Issues**
   - Ensure documents are properly indexed
   - Check document processing status
   - Verify search query format

## Data Privacy

- All processing happens locally
- Documents are stored in temporary directories
- Vector embeddings are stored in ChromaDB
- No data is sent to external services
- Use Reset All to clear all data

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 