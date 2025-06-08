#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import streamlit as st
from rich.console import Console
import tempfile
import logging
import uuid
from datetime import datetime, UTC

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

# Import using absolute paths from src
from src.document_processing.processor import DocumentProcessor
from src.generation.bill_generator import BillGenerator
from src.graph.operations import Neo4jGraph
from src.models.domain import LegalCase
from src.config import DEFAULT_FIRM_ID, DEFAULT_CLIENT_PARTY_ID

console = Console()

# Configure logging to capture in Streamlit
class StreamlitHandler(logging.Handler):
    def __init__(self, container):
        super().__init__()
        self.container = container
        self.logs = []
        
    def emit(self, record):
        log_entry = self.format(record)
        self.logs.append(log_entry)
        # Keep only last 1000 logs
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
        # Update the container
        self.container.text_area("Processing Logs", "\n".join(self.logs), height=300)

def init_session_state():
    """Initialize session state variables."""
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {}
    if 'failed_files' not in st.session_state:
        st.session_state.failed_files = []
    if 'is_processing' not in st.session_state:
        st.session_state.is_processing = False
    if 'overall_progress' not in st.session_state:
        st.session_state.overall_progress = 0

def process_document(processor, file, progress_bar, status_text, index, total_files):
    """Process a single document and return its status."""
    try:
        def update_status(message):
            status_text.text(f"Processing {file.name}... {message}")
        
        # Save uploaded file temporarily
        file_path = Path(file.name)
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        
        # Process document with status updates
        processor.process_document(str(file_path), status_callback=update_status)
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
        progress = (index + 1) / total_files
        st.session_state.overall_progress = progress
        progress_bar.progress(progress)
        
    return status

def main():
    """Main function to run the Streamlit interface."""
    # Initialize session state
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {}
    if 'failed_files' not in st.session_state:
        st.session_state.failed_files = []
    if 'current_case' not in st.session_state:
        st.session_state.current_case = None

    # Initialize components
    graph_ops = Neo4jGraph()
    processor = DocumentProcessor(graph_ops)
    bill_generator = BillGenerator(graph_ops)

    # Custom CSS
    st.markdown("""
        <style>
        .success-box {
            background-color: #d4edda;
            color: #155724;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .error-box {
            background-color: #f8d7da;
            color: #721c24;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .info-box {
            background-color: #cce5ff;
            color: #004085;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }
        </style>
    """, unsafe_allow_html=True)

    # Title and description
    st.title("Legal Cost Drafting Assistant")
    st.markdown("""
        Upload your case documents to extract work items and disbursements.
        The system will process the documents and create a structured record of all billable items.
    """)

    # Case reference input
    st.header("Case Information")
    case_reference = st.text_input("Case Reference", help="Enter the case reference number")
    
    if case_reference:
        # Check if case exists
        existing_case = graph_ops.find_case_by_reference(case_reference)
        if existing_case:
            st.markdown(f"""
                <div class="info-box">
                    Found existing case: {case_reference}<br>
                    Title: {existing_case.case_name}
                </div>
            """, unsafe_allow_html=True)
            st.session_state.current_case = existing_case
        else:
            st.markdown(f"""
                <div class="info-box">
                    No case found with reference: {case_reference}<br>
                    Please create a new case below.
                </div>
            """, unsafe_allow_html=True)
            
            # Case creation form
            with st.form("create_case_form"):
                st.subheader("Create New Case")
                case_name = st.text_input("Case Name", help="Enter the case name (e.g., Smith v Jones)")
                
                if st.form_submit_button("Create Case"):
                    try:
                        # Create new case with hardcoded values
                        new_case = LegalCase(
                            case_id=uuid.uuid4(),
                            case_reference_number=case_reference,  # Use the entered reference
                            case_name=case_name,
                            our_firm_id=DEFAULT_FIRM_ID,
                            our_client_party_id=DEFAULT_CLIENT_PARTY_ID,
                            # Optional fields with defaults
                            court_claim_number=None,
                            court_details_id=None,
                            date_opened=datetime.now(UTC).date(),
                            date_closed=None,
                            status="Open",
                            parties=[],
                            fee_earners_involved_ids=[],
                            counsels_instructed_ids=[],
                            experts_instructed_ids=[],
                            retainer_details_id=None,
                            key_dates={},
                            narrative_summary="Test case for POC",
                            source_documents=[],
                            work_items=[],
                            disbursements=[],
                            bill_of_costs_ids=[],
                            schedule_of_costs_ids=[],
                            precedent_h_ids=[]
                        )
                        
                        # Store case in Neo4j
                        case_id = graph_ops.create_case(new_case)
                        st.markdown(f"""
                            <div class="success-box">
                                Successfully created case: {case_reference}<br>
                                Title: {case_name}
                            </div>
                        """, unsafe_allow_html=True)
                        st.session_state.current_case = new_case
                        st.rerun()
                        
                    except Exception as e:
                        st.markdown(f"""
                            <div class="error-box">
                                Error creating case: {str(e)}
                            </div>
                        """, unsafe_allow_html=True)

    # File upload section - only show if we have a current case
    if st.session_state.current_case:
        st.header("Document Upload")
        uploaded_files = st.file_uploader(
            "Upload your documents",
            type=['pdf', 'docx', 'txt', 'eml'],
            accept_multiple_files=True
        )

        # Create a container for logs
        log_container = st.empty()
        # Set up logging to Streamlit
        handler = StreamlitHandler(log_container)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger = logging.getLogger()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Process documents button
        if uploaded_files and st.button("Process Documents"):
            total_files = len(uploaded_files)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                try:
                    # Save uploaded file to temporary location
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name
                    
                    # Update status
                    status_text.text(f"Processing {uploaded_file.name}...")
                    logger.info(f"Starting processing of {uploaded_file.name}")
                    
                    # Process document with status updates
                    def update_status(message):
                        status_text.text(f"Processing {uploaded_file.name}... {message}")
                        logger.info(f"{uploaded_file.name}: {message}")
                    
                    result = processor.process_document(tmp_path, legal_case=st.session_state.current_case, status_callback=update_status)
                    
                    # Update progress
                    progress = (i + 1) / total_files
                    progress_bar.progress(progress)
                    
                    # Show success message
                    st.markdown(f"""
                        <div class="success-box">
                            Successfully processed {uploaded_file.name}<br>
                            Found {len(result['work_items'])} work items and {len(result['disbursements'])} disbursements
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Clean up temporary file
                    os.unlink(tmp_path)
                    
                except Exception as e:
                    logger.error(f"Error processing {uploaded_file.name}: {str(e)}", exc_info=True)
                    st.markdown(f"""
                        <div class="error-box">
                            Error processing {uploaded_file.name}: {str(e)}
                        </div>
                    """, unsafe_allow_html=True)
                    st.session_state.failed_files.append(uploaded_file.name)
            
            # Show final status
            if st.session_state.failed_files:
                st.markdown(f"""
                    <div class="error-box">
                        Failed to process {len(st.session_state.failed_files)} files:<br>
                        {', '.join(st.session_state.failed_files)}
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div class="success-box">
                        All documents processed successfully!
                    </div>
                """, unsafe_allow_html=True)

        # Generate Bill section
        st.header("Generate Bill")
        if st.button("Generate Bill"):
            try:
                with st.spinner("Generating bill..."):
                    bill = bill_generator.generate_bill(st.session_state.current_case.case_id)
                    st.markdown(f"""
                        <div class="success-box">
                            Bill generated successfully!<br>
                            Total work items: {len(bill.work_items)}<br>
                            Total disbursements: {len(bill.disbursements)}<br>
                            Total amount: £{bill.total_amount:.2f}
                        </div>
                    """, unsafe_allow_html=True)
            except Exception as e:
                st.markdown(f"""
                    <div class="error-box">
                        Error generating bill: {str(e)}
                    </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main() 