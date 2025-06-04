# Legal RAG Document Generator

A Streamlit-based application that uses RAG (Retrieval-Augmented Generation) to generate legal documents based on uploaded case materials. The application uses specialized prompts to ensure compliance with UK legal standards and CPR rules.

## Prerequisites

- macOS (tested on M4 MacBook Pro)
- Python 3.9+
- Ollama installed and running
- 48GB RAM (recommended for optimal performance)

## Installation

1. Install Ollama:
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

2. Pull required models:
```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

3. Create and activate virtual environment:
```bash
python -m venv legal_rag_env
source legal_rag_env/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Start Ollama:
```bash
ollama serve
```

2. In a new terminal, run the Streamlit app:
```bash
streamlit run app.py
```

## Usage

1. Upload your legal documents using the sidebar uploader
   - Supported formats: PDF, TXT, DOCX, MD
   - Documents will be automatically indexed

2. Select the type of document you want to generate:
   - Bill of Costs
   - Court Narrative
   - Schedule of Work
   - Data Extraction Summary

3. Enter your specific requirements or additional context
   - Include case type, court level, value range
   - Specify any special circumstances
   - Add any specific formatting requirements

4. Click "Generate Document"
   - The system will process your documents
   - Apply the specialized prompt template
   - Generate a compliant document

5. Download the generated document using the download button

## Supported Document Types

- **Bill of Costs**: Detailed breakdown following CPR 47
  - Solicitor's charges
  - Counsel's fees
  - Disbursements
  - VAT calculations
  - Percentage uplifts

- **Court Narrative**: Comprehensive case story for assessment
  - Case overview
  - Chronological account
  - Costs issues
  - Work justification

- **Schedule of Work**: Chronological work breakdown by phases
  - Pre-action to enforcement
  - Detailed time entries
  - Fee earner details
  - Work categorization

- **Data Extraction Summary**: Key metrics and financial analysis
  - Time ledger analysis
  - Correspondence summary
  - Court orders review
  - Cost implications

## Project Structure

```
.
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── legal_docs/           # Directory for legal documents
├── storage/              # Vector store persistence
└── README.md             # This file
```

## Troubleshooting

### Common Issues

1. **Ollama Connection Errors**
   - Ensure Ollama is running with `ollama serve`
   - Check if models are installed with `ollama list`
   - Verify model names match: `llama3.1:8b` and `nomic-embed-text`

2. **Memory Issues**
   - Close other applications to free RAM
   - Consider using smaller models if needed
   - Monitor system resources during document processing

3. **Slow Performance**
   - Ensure you're using GPU acceleration if available
   - Reduce the size of uploaded documents
   - Consider processing documents in smaller batches

4. **Document Generation Issues**
   - Ensure uploaded documents contain relevant information
   - Provide clear and specific requirements
   - Check document format compatibility

## Data Privacy

- All processing happens locally on your machine
- No data is sent to external services
- Vector embeddings are stored locally in `./storage/`
- Documents remain in your `./legal_docs/` directory
- Generated documents are temporary and not stored 