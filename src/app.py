import streamlit as st
import os
from pathlib import Path
import sys
from typing import List, Optional
import logging
import tempfile
import shutil
import time

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from src.models.domain import LegalCase, DocumentType
from src.graph.operations import Neo4jGraph
from src.document_processing.processor import DocumentProcessor
from src.generation.generator import DocumentGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def save_uploaded_files(uploaded_files):
    """Save uploaded files to a temporary directory."""
    temp_dir = tempfile.mkdtemp()
    saved_paths = []
    
    for uploaded_file in uploaded_files:
        file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(file_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        saved_paths.append(file_path)
    
    return temp_dir, saved_paths

def process_documents(directory_path: str, case_reference: str, legal_case: Optional[LegalCase] = None) -> List[dict]:
    """Process all documents in a directory with progress tracking."""
    if not case_reference and not legal_case:
        st.error("Either case_reference or legal_case must be provided")
        return []
        
    processor = DocumentProcessor(Neo4jGraph())
    
    # Get list of valid documents
    valid_extensions = ['.pdf', '.txt', '.md']
    documents = [f for f in Path(directory_path).glob('*') 
                if f.suffix.lower() in valid_extensions]
    total_docs = len(documents)
    
    if total_docs == 0:
        st.warning("No valid documents found in the selected directory.")
        return []
    
    # Use st.empty() for progress bar and status
    progress_bar_container = st.empty()
    status_text_container = st.empty()
    
    results = []
    start_time = time.time()
    for i, doc_path in enumerate(documents, 1):
        try:
            # Update progress
            progress = (i - 1) / total_docs
            progress_bar_container.progress(progress)
            status_text_container.text(f"Processing {i}/{total_docs}: {doc_path.name}")
            
            # Process document
            result = processor.process_document(
                str(doc_path),
                legal_case,
                case_reference,
                status_callback=lambda msg: status_text_container.text(f"Processing {i}/{total_docs}: {doc_path.name} - {msg}")
            )
            results.append(result)
            
        except Exception as e:
            logger.error(f"Error processing {doc_path}: {str(e)}")
            st.error(f"Error processing {doc_path.name}: {str(e)}")
            continue
        # Sleep briefly to allow UI to update
        time.sleep(0.1)
    
    # Complete progress bar
    progress_bar_container.progress(1.0)
    status_text_container.text("Processing complete!")
    
    elapsed = time.time() - start_time
    st.success(f"All documents processed successfully! Processed {total_docs} document(s) in {elapsed:.1f} seconds.")
    
    return results

def generate_documents(case_id: str, document_types: List[DocumentType]) -> List[str]:
    """Generate specified document types for a case."""
    generator = DocumentGenerator()
    generated_files = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, doc_type in enumerate(document_types, 1):
        try:
            # Update progress
            progress = (i - 1) / len(document_types)
            progress_bar.progress(progress)
            status_text.text(f"Generating {i}/{len(document_types)}: {doc_type.value}")
            
            # Generate document
            doc = generator.generate_document(case_id, doc_type)
            file_path = generator.save_document(doc, case_id, doc_type)
            generated_files.append(file_path)
            
        except Exception as e:
            logger.error(f"Error generating {doc_type.value}: {str(e)}")
            st.error(f"Error generating {doc_type.value}: {str(e)}")
            continue
    
    # Complete progress bar
    progress_bar.progress(1.0)
    status_text.text("Generation complete!")
    
    return generated_files

def main():
    st.title("AI Costing Graph - Document Processor")
    
    # File upload section
    st.header("Upload Documents")
    uploaded_files = st.file_uploader(
        "Choose files to process",
        type=['pdf', 'txt', 'md'],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        # Create two columns for buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Process Documents"):
                with st.spinner("Processing documents..."):
                    # Save uploaded files
                    temp_dir, saved_paths = save_uploaded_files(uploaded_files)
                    
                    try:
                        # Process documents
                        results = process_documents(temp_dir)
                        
                        # Display results
                        if results:
                            st.success(f"Successfully processed {len(results)} documents")
                            
                            # Show summary
                            st.subheader("Processing Summary")
                            for result in results:
                                doc = result['document']
                                st.write(f"Document: {doc.file_name}")
                                st.write(f"- Work Items: {len(result['work_items'])}")
                                st.write(f"- Disbursements: {len(result['disbursements'])}")
                                st.write("---")
                        else:
                            st.warning("No documents were processed successfully")
                            
                    finally:
                        # Clean up temporary directory
                        shutil.rmtree(temp_dir)
        
        with col2:
            if st.button("Generate Documents"):
                with st.spinner("Generating documents..."):
                    # Get case ID from session state or input
                    case_id = st.session_state.get('current_case_id')
                    if not case_id:
                        case_id = st.text_input("Enter Case ID")
                        if not case_id:
                            st.error("Please enter a Case ID")
                            return
                    
                    # Document type selection
                    doc_types = st.multiselect(
                        "Select document types to generate",
                        options=[dt.value for dt in DocumentType],
                        default=[DocumentType.BILL_OF_COSTS.value]
                    )
                    
                    if doc_types:
                        # Generate documents
                        generated_files = generate_documents(
                            case_id,
                            [DocumentType(dt) for dt in doc_types]
                        )
                        
                        # Display results
                        if generated_files:
                            st.success(f"Successfully generated {len(generated_files)} documents")
                            
                            # Show generated files
                            st.subheader("Generated Documents")
                            for file_path in generated_files:
                                st.write(f"- {os.path.basename(file_path)}")
                        else:
                            st.warning("No documents were generated successfully")

if __name__ == "__main__":
    main() 