from typing import List, Optional, Dict, Any
import os
from pathlib import Path
import uuid
from datetime import datetime
from langchain.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

from ..models.domain import DocumentChunk, Case
from ..llm.operations import LLMOperations
from ..graph.operations import Neo4jGraph

class DocumentProcessor:
    def __init__(self):
        """Initialize document processor with LLM and graph operations."""
        self.llm_ops = LLMOperations()
        self.graph = Neo4jGraph()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False
        )
    
    def load_document(self, file_path: str) -> str:
        """Load document content based on file type."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if file_path.suffix.lower() == '.pdf':
            loader = PyPDFLoader(str(file_path))
            pages = loader.load()
            return "\n".join(page.page_content for page in pages)
        elif file_path.suffix.lower() in ['.txt', '.md']:
            loader = TextLoader(str(file_path))
            return loader.load()[0].page_content
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
    
    def create_document_chunks(self, content: str, file_path: str, case_id: Optional[str] = None) -> List[DocumentChunk]:
        """Create document chunks from content."""
        chunks = self.text_splitter.split_text(content)
        return [
            DocumentChunk(
                id=str(uuid.uuid4()),
                content=chunk,
                source_file=str(file_path),
                page_number=i + 1,
                chunk_index=i,
                created_at=datetime.now(),
                case_id=case_id
            )
            for i, chunk in enumerate(chunks)
        ]
    
    def extract_case_info(self, text: str) -> Case:
        """Extract case information from document content."""
        # Use LLM to extract case information
        prompt = PromptTemplate(
            input_variables=["text"],
            template="""
            Extract case information from the following text. If any information is not found, use reasonable defaults.
            Return the information in this exact format:
            Case Reference: [reference or generate a unique reference]
            Title: [title or "Untitled Case"]
            Court: [court name or "Unknown Court"]
            Description: [brief description or "No description available"]

            Text:
            {text}
            """
        )
        
        # Use the new RunnablePassthrough pattern
        chain = prompt | self.llm_ops.llm
        
        result = chain.invoke({"text": text})
        
        # Parse the result
        lines = result.strip().split('\n')
        case_info = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                case_info[key.strip()] = value.strip()
        
        # Generate a case reference if none was found
        if 'Case Reference' not in case_info or not case_info['Case Reference']:
            case_info['Case Reference'] = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        
        return Case(
            id=str(uuid.uuid4()),
            reference=case_info.get('Case Reference', f"CASE-{uuid.uuid4().hex[:8].upper()}"),
            title=case_info.get('Title', 'Untitled Case'),
            court=case_info.get('Court', 'Unknown Court'),
            description=case_info.get('Description', 'No description available'),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    def process_document(self, file_path: str, case: Optional[Case] = None) -> List[DocumentChunk]:
        """Process a document and store its chunks in the graph database."""
        with self.graph as graph:
            # Check if document already exists
            if graph.document_exists(file_path):
                raise ValueError(f"Document already processed: {file_path}")
            
            # Load and chunk document
            content = self.load_document(file_path)
            
            # Extract case information if not provided
            if not case:
                # Create a temporary chunk to extract case info
                temp_chunks = self.create_document_chunks(content, file_path)
                case = self.extract_case_info(temp_chunks[0].content)
                case = graph.find_or_create_case(case)
            
            # Create chunks with case_id
            chunks = self.create_document_chunks(content, file_path, case.id)
            
            # Store chunks in database
            for chunk in chunks:
                graph.create_document_chunk(chunk, case)
            
            return chunks
    
    def process_directory(self, directory_path: str, case: Optional[Case] = None) -> List[DocumentChunk]:
        """Process all documents in a directory."""
        all_chunks = []
        with self.graph as graph:
            for file_path in Path(directory_path).glob('*'):
                if file_path.suffix.lower() in ['.pdf', '.txt', '.md']:
                    try:
                        chunks = self.process_document(str(file_path), case)
                        all_chunks.extend(chunks)
                    except Exception as e:
                        print(f"Error processing {file_path}: {str(e)}")
        return all_chunks 