#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import streamlit as st
from rich.console import Console

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

# Import using absolute paths from src
from src.document_processing.processor import DocumentProcessor
from src.generation.bill_generator import BillGenerator
from src.graph.operations import Neo4jGraph

console = Console()

def init_session_state():
    """Initialize session state variables."""
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {}
    if 'failed_files' not in st.session_state:
        st.session_state.failed_files = []

def process_document(processor, file, progress_bar, status_text, index, total_files):
    """Process a single document and return its status."""
    try:
        status_text.text(f"Processing {file.name}...")
        
        # Save uploaded file temporarily
        file_path = Path(file.name)
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        
        # Process document
        processor.process_document(str(file_path))
        status = "success"
        
    except ValueError as e:
        status = f"warning: {str(e)}"
    except Exception as e:
        status = f"error: {str(e)}"
    finally:
        # Clean up uploaded file
        if file_path.exists():
            os.remove(file_path)
        
        # Update progress
        progress_bar.progress((index + 1) / total_files)
        
    return status

def main():
    st.set_page_config(
        page_title="Legal Cost Management System",
        page_icon="⚖️",
        layout="wide"
    )
    
    # Initialize session state
    init_session_state()
    
    # Initialize components
    processor = DocumentProcessor()
    bill_generator = BillGenerator()
    graph = Neo4jGraph()
    
    # Custom CSS
    st.markdown("""
        <style>
        .main {
            padding: 2rem;
        }
        .stButton>button {
            width: 100%;
            margin-top: 1rem;
        }
        .success-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #d4edda;
            color: #155724;
            margin: 1rem 0;
        }
        .error-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #f8d7da;
            color: #721c24;
            margin: 1rem 0;
        }
        .info-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #cce5ff;
            color: #004085;
            margin: 1rem 0;
        }
        .reprocess-button {
            background-color: #ffc107;
            color: #000;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Choose a page", ["Document Upload", "Generate Bill"])
    
    if page == "Document Upload":
        st.title("📄 Document Upload")
        st.markdown("""
        Upload legal documents (PDF, DOCX, emails, TXT) to ingest them into the system. 
        Case information will be automatically extracted from the documents.
        """)
        
        # File uploader with drag and drop
        uploaded_files = st.file_uploader(
            "Drag and drop files here or click to browse",
            accept_multiple_files=True,
            type=["pdf", "docx", "txt", "eml"],
            help="Supported formats: PDF, DOCX, TXT, EML"
        )
        
        if uploaded_files:
            st.session_state.uploaded_files = uploaded_files
            st.info(f"Selected {len(uploaded_files)} file(s)")
            
            # Show file details
            with st.expander("File Details", expanded=True):
                for file in uploaded_files:
                    st.write(f"📄 {file.name} ({file.size / 1024:.1f} KB)")
        
        # Process Documents button
        if st.button("Process Documents", type="primary"):
            if not st.session_state.uploaded_files:
                st.error("Please upload at least one document.")
                return
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Process uploaded documents
            for i, uploaded_file in enumerate(st.session_state.uploaded_files):
                status = process_document(
                    processor, 
                    uploaded_file, 
                    progress_bar, 
                    status_text, 
                    i, 
                    len(st.session_state.uploaded_files)
                )
                st.session_state.processing_status[uploaded_file.name] = status
                
                # Track failed files
                if status.startswith("error"):
                    st.session_state.failed_files.append(uploaded_file)
            
            # Show processing results
            st.markdown("### Processing Results")
            for filename, status in st.session_state.processing_status.items():
                if status == "success":
                    st.markdown(f'<div class="success-box">✅ {filename}: Successfully processed</div>', unsafe_allow_html=True)
                elif status.startswith("warning"):
                    st.markdown(f'<div class="info-box">⚠️ {filename}: {status[8:]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="error-box">❌ {filename}: {status[6:]}</div>', unsafe_allow_html=True)
            
            # Show reprocess button if there are failed files
            if st.session_state.failed_files:
                st.markdown("### Failed Documents")
                st.warning(f"{len(st.session_state.failed_files)} documents failed to process.")
                if st.button("🔄 Reprocess Failed Documents", type="secondary"):
                    # Create progress bar for reprocessing
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Process only failed documents
                    for i, failed_file in enumerate(st.session_state.failed_files):
                        status = process_document(
                            processor, 
                            failed_file, 
                            progress_bar, 
                            status_text, 
                            i, 
                            len(st.session_state.failed_files)
                        )
                        st.session_state.processing_status[failed_file.name] = status
                    
                    # Clear failed files list
                    st.session_state.failed_files = []
                    
                    # Show updated results
                    st.markdown("### Updated Processing Results")
                    for filename, status in st.session_state.processing_status.items():
                        if status == "success":
                            st.markdown(f'<div class="success-box">✅ {filename}: Successfully processed</div>', unsafe_allow_html=True)
                        elif status.startswith("warning"):
                            st.markdown(f'<div class="info-box">⚠️ {filename}: {status[8:]}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="error-box">❌ {filename}: {status[6:]}</div>', unsafe_allow_html=True)
    
    else:  # Generate Bill page
        st.title("💰 Generate Bill of Costs")
        st.markdown("""
        Generate a professional bill of costs for your case. 
        Select a case from the dropdown below to get started.
        """)
        
        # Get list of cases from Neo4j
        try:
            cases = graph.get_all_cases()
            if not cases:
                st.warning("No cases found in the database. Please upload some documents first.")
                return
            
            # Case selection with better formatting
            case_options = {f"{case.reference} - {case.title}": case.id for case in cases}
            selected_case = st.selectbox(
                "Select a case",
                options=list(case_options.keys()),
                help="Choose the case for which you want to generate a bill"
            )
            
            if st.button("Generate Bill", type="primary"):
                try:
                    with st.spinner("Generating bill..."):
                        # Generate bill
                        case_id = case_options[selected_case]
                        bill_html = bill_generator.generate_bill(case_id)
                        
                        # Save bill
                        case = graph.get_case(case_id)
                        file_path = bill_generator.save_bill(bill_html, case)
                        
                        # Success message
                        st.success("Bill generated successfully!")
                        
                        # Download button
                        st.download_button(
                            label="📥 Download Bill",
                            data=bill_html,
                            file_name=file_path.name,
                            mime="text/html",
                            help="Click to download the generated bill"
                        )
                        
                        # Preview
                        st.markdown("### Bill Preview")
                        st.components.v1.html(bill_html, height=800, scrolling=True)
                        
                except Exception as e:
                    st.error(f"Error generating bill: {str(e)}")
                    
        except Exception as e:
            st.error(f"Error loading cases: {str(e)}")

if __name__ == "__main__":
    main() 