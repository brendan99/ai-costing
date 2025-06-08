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
from typing import Dict, Any
import base64

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

def is_valid_uuid(uuid_str: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(uuid_str)
        return True
    except ValueError:
        return False

def retrieve_case_details(case_id: str) -> Dict[str, Any]:
    """Retrieve details of an existing case from the database."""
    if not is_valid_uuid(case_id):
        st.error("Invalid Case ID format. Please enter a valid UUID.")
        return None
        
    graph_ops = Neo4jGraph()
    case = graph_ops.get_case(case_id)
    if not case:
        st.error(f"Case not found with ID: {case_id}")
        return None
    return case

def display_case_details(case_details: Dict[str, Any]):
    """Display case details in a user-friendly format."""
    if not case_details:
        return
        
    st.subheader("Case Information")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Case ID:**", case_details.get("case_id"))
        st.write("**Case Name:**", case_details.get("case_name"))
        st.write("**Case Type:**", case_details.get("case_type"))
        st.write("**Status:**", case_details.get("status"))
    
    with col2:
        st.write("**Created:**", case_details.get("created_at"))
        st.write("**Updated:**", case_details.get("updated_at"))
        st.write("**Reference:**", case_details.get("case_reference_number"))
    
    # Display work items
    if case_details.get("work_items"):
        st.subheader("Work Items")
        for item in case_details["work_items"]:
            with st.expander(f"{item.get('activity_type', 'Unknown Activity')} - {item.get('date', 'No date')}"):
                st.write("**Description:**", item.get("description", "No description"))
                st.write("**Time Spent:**", f"{item.get('time_spent_decimal_hours', 0)} hours")
                st.write("**Amount:**", f"£{item.get('claimed_amount_gbp', 0):.2f}")
    
    # Display disbursements
    if case_details.get("disbursements"):
        st.subheader("Disbursements")
        for disb in case_details["disbursements"]:
            with st.expander(f"{disb.get('disbursement_type', 'Unknown Type')} - {disb.get('date_incurred', 'No date')}"):
                st.write("**Description:**", disb.get("description", "No description"))
                st.write("**Amount:**", f"£{disb.get('amount_gross_gbp', 0):.2f}")
                st.write("**VAT:**", f"£{disb.get('vat_gbp', 0):.2f}")

def retrieve_case_by_reference(reference: str) -> Dict[str, Any]:
    """Retrieve details of an existing case from the database using reference number."""
    graph_ops = Neo4jGraph()
    case = graph_ops.find_case_by_reference(reference)
    if not case:
        st.error(f"Case not found with reference: {reference}")
        return None
    return case.model_dump()

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

    st.title("UK Legal Costing RAG System")

    # Sidebar for document upload
    st.sidebar.header("Document Upload")
    uploaded_files = st.sidebar.file_uploader("Upload legal documents", type=["pdf", "txt", "docx", "md"], accept_multiple_files=True)
    if uploaded_files:
        st.session_state.uploaded_files = uploaded_files

    # Main content area
    st.header("Document Processing")
    if st.session_state.uploaded_files:
        st.write(f"Uploaded {len(st.session_state.uploaded_files)} files")
        for file in st.session_state.uploaded_files:
            st.write(f"- {file.name}")

    # Retrieve existing case details
    st.header("Retrieve Existing Case")
    st.markdown("""
        <div class="info-box">
            Enter either a case reference number or UUID to retrieve case details.
        </div>
    """, unsafe_allow_html=True)
    
    # Create two columns for input methods
    col1, col2 = st.columns(2)
    
    with col1:
        case_reference = st.text_input("Enter Case Reference Number", 
                                     help="Enter the reference number of the case you want to retrieve")
        if case_reference:
            case_details = retrieve_case_by_reference(case_reference)
            if case_details:
                display_case_details(case_details)
                st.session_state.current_case = case_details
    
    with col2:
        case_id = st.text_input("Enter Case ID (UUID)", 
                               help="Enter the UUID of the case you want to retrieve")
        if case_id:
            if is_valid_uuid(case_id):
                case_details = retrieve_case_details(case_id)
                if case_details:
                    display_case_details(case_details)
                    st.session_state.current_case = case_details
            else:
                st.error("Please enter a valid UUID in the format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

    # Generate bill button and download button side by side
    bill_generated = False
    bill_html = None
    bill_path = None
    if st.session_state.get('current_case'):
        colA, colB = st.columns([1,1])
        with colA:
            generate_clicked = st.button("Generate Bill")
        with colB:
            # Placeholder for download button, will be enabled after bill is generated
            download_placeholder = st.empty()
    else:
        generate_clicked = st.button("Generate Bill")
        download_placeholder = st.empty()

    if generate_clicked and st.session_state.current_case:
        with st.spinner("Generating bill..."):
            try:
                bill = bill_generator.generate_bill(st.session_state.current_case["case_id"])
                st.success(f"Bill generated successfully. Total amount: £{bill.total_amount:.2f}, Recoverable: £{bill.recoverable_amount:.2f}")
                bill_path = bill_generator.save_bill(bill)
                with open(bill_path, 'r', encoding='utf-8') as f:
                    bill_html = f.read()
                bill_generated = True
            except Exception as e:
                st.error(f"Error generating bill: {str(e)}")

    # Show download button if bill was generated
    if bill_generated and bill_html and bill_path:
        download_placeholder.download_button(
            label="Download Bill of Costs",
            data=bill_html,
            file_name=os.path.basename(bill_path),
            mime="text/html"
        )
        # Full-width preview below
        st.markdown("---")
        st.markdown("### Bill Preview")
        st.components.v1.iframe(
            f"data:text/html;base64,{base64.b64encode(bill_html.encode()).decode()}",
            height=900,
            width=None,
            scrolling=True
        )

if __name__ == "__main__":
    main() 