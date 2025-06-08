from typing import List, Optional, Dict, Any, Tuple
import os
from pathlib import Path
import uuid
from datetime import datetime, date
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
import json
import time
import logging
import re

from ..models.domain import (
    LegalCase, SourceDocument, DocumentChunk, WorkItem, Disbursement, FeeEarner, Party,
    DocumentType, ActivityType, DisbursementType
)
from ..llm.operations import LLMOperations
from ..graph.operations import Neo4jGraph
from src.config import DEFAULT_FIRM_ID, DEFAULT_CLIENT_PARTY_ID

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, graph_ops):
        """Initialize document processor with graph operations."""
        self.graph_ops = graph_ops
        self.llm_ops = LLMOperations()
        self.current_case_id = None
        self.current_fee_earner_id = None
        logger.info("DocumentProcessor initialized")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False
        )
        self.default_firm_id = DEFAULT_FIRM_ID
        self.default_client_party_id = DEFAULT_CLIENT_PARTY_ID
        logger.info(f"Using default firm ID: {self.default_firm_id}")
        logger.info(f"Using default client party ID: {self.default_client_party_id}")
    
    def process_document(self, file_path: str, legal_case: Optional[LegalCase] = None, case_reference: Optional[str] = None, status_callback=None) -> Dict[str, Any]:
        """Process a document and extract structured information."""
        try:
            logger.info(f"Starting to process document: {file_path}")
            
            # Load document content first
            content = self.load_document(file_path)
            logger.info(f"Document loaded, content length: {len(content)}")
            
            # Set current case ID if provided or find case by reference
            if legal_case:
                self.current_case_id = legal_case.case_id
                logger.info(f"Using provided case ID: {self.current_case_id}")
            elif case_reference:
                # Try to find existing case by reference
                existing_case = self.graph_ops.find_case_by_reference(case_reference)
                if existing_case:
                    self.current_case_id = existing_case.case_id
                    logger.info(f"Found existing case with ID: {self.current_case_id}")
                else:
                    raise ValueError(f"No case found with reference: {case_reference}")
            else:
                raise ValueError("Either legal_case or case_reference must be provided")
            
            if status_callback:
                status_callback("Creating document record...")
            
            document = SourceDocument(
                document_id=str(uuid.uuid4()),
                case_id=self.current_case_id,
                file_name=os.path.basename(file_path),
                document_type=DocumentType.OTHER_INPUT,
                content=content,
                created_at=datetime.now()
            )
            logger.info(f"Document record created with ID: {document.document_id}")
            
            # Extract structured entities (work items, disbursements)
            if status_callback:
                status_callback("Extracting work items and disbursements...")
            logger.info("Starting entity extraction")
            entities = self.extract_structured_entities(content, status_callback)
            work_items = entities[0]
            disbursements = entities[1]
            logger.info(f"Extracted {len(work_items)} work items and {len(disbursements)} disbursements")
            
            # Create document chunks
            if status_callback:
                status_callback("Creating document chunks...")
            logger.info("Starting chunk creation")
            chunks = self.create_document_chunks(document, content)
            logger.info(f"Created {len(chunks)} document chunks")
            
            # Store in graph database
            if status_callback:
                status_callback("Storing in database...")
            logger.info("Starting database storage")
            
            # Store document
            self.graph_ops.store_document(document)
            logger.info("Document stored in database")
            
            # Store chunks
            for chunk in chunks:
                self.graph_ops.create_document_chunk(chunk, legal_case)
            logger.info("Document chunks stored in database")
            
            # Store work items
            for work_item in work_items:
                self.graph_ops.create_work_item(self.current_case_id, work_item)
            logger.info("Work items stored in database")
            
            # Store disbursements
            for disbursement in disbursements:
                self.graph_ops.create_disbursement(self.current_case_id, disbursement)
            logger.info("Disbursements stored in database")
            
            if status_callback:
                status_callback("Processing complete!")
            
            return {
                "document": document,
                "chunks": chunks,
                "work_items": work_items,
                "disbursements": disbursements
            }
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}", exc_info=True)
            if status_callback:
                status_callback(f"Error: {str(e)}")
            raise
    
    def load_document(self, file_path: str) -> str:
        """Load document content based on file type."""
        try:
            logger.info(f"Loading document: {file_path}")
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.pdf':
                loader = PyPDFLoader(file_path)
                pages = loader.load()
                content = "\n".join(page.page_content for page in pages)
            elif file_extension == '.txt':
                loader = TextLoader(file_path)
                content = loader.load()[0].page_content
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            logger.info(f"Document loaded successfully, content length: {len(content)}")
            return content
            
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {str(e)}", exc_info=True)
            raise
    
    def create_document_chunks(self, document: SourceDocument, content: str) -> List[DocumentChunk]:
        """Create document chunks from content."""
        try:
            logger.info("Creating document chunks")
            chunks = []
            text_chunks = self.text_splitter.split_text(content)
            
            for i, chunk_text in enumerate(text_chunks):
                chunk = DocumentChunk(
                    chunk_id=uuid.uuid4(),
                    source_document_id=document.document_id,
                    text_content=chunk_text,
                    page_number_start=None,  # These could be populated if we track page numbers
                    page_number_end=None,
                    embedding=None,  # This will be populated later if needed
                    metadata={"chunk_index": i}
                )
                chunks.append(chunk)
            
            logger.info(f"Created {len(chunks)} document chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error creating document chunks: {str(e)}", exc_info=True)
            raise
    
    def extract_structured_entities(self, text: str, status_callback=None) -> Tuple[List[WorkItem], List[Disbursement]]:
        """Extract structured entities from text using LLM."""
        work_items = []
        disbursements = []
        
        # Extract work items
        if status_callback:
            status_callback("Extracting work items...")
        logger.info("Starting work items extraction")
        
        work_items_prompt = f"""Extract work items from the following text. For each work item, provide:
        - date_of_work (YYYY-MM-DD)
        - activity_type (must be one of: {', '.join([t.value for t in ActivityType])})
        - description
        - time_spent_units (integer, default to 0 if not specified)
        - time_spent_decimal_hours (float, default to 0.0 if not specified)
        - applicable_hourly_rate_gbp (float, default to 0.0 if not specified)
        - claimed_amount_gbp (float, default to 0.0 if not specified)
        - is_recoverable (boolean, default to true if not specified)

        IMPORTANT:
        - All numeric fields must be valid numbers, not null or undefined
        - If a numeric value is not provided, use 0 or 0.0 as appropriate
        - Do not include comments in the JSON response
        - Do not include trailing commas
        - Ensure all dates are in YYYY-MM-DD format
        - Return a valid JSON array without any additional text or formatting
        - Do not include ellipsis (...) in the response
        - Do not include trailing commas after the last item in arrays or objects

        Text: {text}

        Return as a JSON array of work items."""

        work_items_response = self.llm_ops.llm.invoke(work_items_prompt)
        logger.info("Received work items response from LLM")
        
        try:
            # Clean the response to ensure valid JSON
            cleaned_response = work_items_response.strip()
            
            # Remove any comments
            cleaned_response = re.sub(r'//.*$', '', cleaned_response, flags=re.MULTILINE)
            
            # Remove trailing commas in arrays and objects
            cleaned_response = re.sub(r',(\s*[}\]])', r'\1', cleaned_response)
            
            # Remove ellipsis
            cleaned_response = re.sub(r'\.\.\.', '', cleaned_response)
            
            # Find the first [ and last ] to extract just the JSON array
            start_idx = cleaned_response.find('[')
            end_idx = cleaned_response.rfind(']') + 1
            if start_idx != -1 and end_idx != -1:
                cleaned_response = cleaned_response[start_idx:end_idx]
            
            # Additional cleaning for common JSON issues
            cleaned_response = re.sub(r',\s*,', ',', cleaned_response)  # Remove multiple consecutive commas
            cleaned_response = re.sub(r'\[\s*,', '[', cleaned_response)  # Remove leading comma in array
            cleaned_response = re.sub(r',\s*\]', ']', cleaned_response)  # Remove trailing comma in array
            cleaned_response = re.sub(r'{\s*,', '{', cleaned_response)  # Remove leading comma in object
            cleaned_response = re.sub(r',\s*}', '}', cleaned_response)  # Remove trailing comma in object
            
            # Parse the cleaned JSON
            work_items_data = json.loads(cleaned_response)
            if not isinstance(work_items_data, list):
                work_items_data = [work_items_data]
            
            logger.info(f"Parsed {len(work_items_data)} work items from LLM response")
            
            for item in work_items_data:
                try:
                    # Map activity type to valid enum value
                    activity_type = item.get('activity_type', '')
                    mapped_activity_type = self._map_activity_type(activity_type)
                    item['activity_type'] = mapped_activity_type
                    
                    # Add required fields
                    item['case_id'] = self.current_case_id
                    
                    # Fix date format if needed
                    if 'date_of_work' in item:
                        item['date_of_work'] = self._fix_date_format(item['date_of_work'])
                    
                    # Convert numeric fields to appropriate types with defaults
                    item['time_spent_units'] = int(item.get('time_spent_units', 0))
                    item['time_spent_decimal_hours'] = float(item.get('time_spent_decimal_hours', 0.0))
                    item['applicable_hourly_rate_gbp'] = float(item.get('applicable_hourly_rate_gbp', 0.0))
                    item['claimed_amount_gbp'] = float(item.get('claimed_amount_gbp', 0.0))
                    
                    # Ensure boolean field is properly set
                    item['is_recoverable'] = bool(item.get('is_recoverable', True))
                    
                    work_item = WorkItem(**item)
                    work_items.append(work_item)
                    logger.info(f"Successfully created work item: {work_item.description[:50]}...")
                except Exception as e:
                    logger.error(f"Error parsing WorkItem: {e} | Data: {item}")
                    continue
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing work items JSON: {e}")
            logger.error(f"Raw response: {work_items_response}")
            logger.error(f"Cleaned response: {cleaned_response}")
        
        # Extract disbursements
        if status_callback:
            status_callback("Extracting disbursements...")
        logger.info("Starting disbursements extraction")
        
        disbursements_prompt = f"""Extract disbursements from the following text. For each disbursement, provide:
        - date_incurred (YYYY-MM-DD)
        - disbursement_type (must be one of: {', '.join([t.value for t in DisbursementType])})
        - description
        - payee_name
        - amount_net_gbp (REQUIRED: must be a valid number, use 0.0 if not specified)
        - vat_gbp (REQUIRED: must be a valid number, use 0.0 if not specified)
        - amount_gross_gbp (optional: if not specified, will be calculated as amount_net_gbp + vat_gbp)
        - is_recoverable (boolean, default to true if not specified)
        - voucher_document

        IMPORTANT:
        - All numeric fields must be valid numbers, not null or undefined
        - If a numeric value is not provided, use 0.0 as the default
        - Do not include comments in the JSON response
        - Do not include trailing commas
        - Ensure all dates are in YYYY-MM-DD format
        - Do not include ellipsis (...) in the response

        Text: {text}

        Return as a JSON array of disbursements."""

        disbursements_response = self.llm_ops.llm.invoke(disbursements_prompt)
        logger.info("Received disbursements response from LLM")
        
        try:
            # Clean the response to remove any comments, trailing commas, and ellipsis
            cleaned_response = re.sub(r'//.*$', '', disbursements_response, flags=re.MULTILINE)  # Remove comments
            cleaned_response = re.sub(r',\s*]', ']', cleaned_response)  # Remove trailing commas
            cleaned_response = re.sub(r',\s*}', '}', cleaned_response)  # Remove trailing commas in objects
            cleaned_response = re.sub(r'\.\.\.', '', cleaned_response)  # Remove ellipsis
            
            # Find the first [ and last ] to extract just the JSON array
            start_idx = cleaned_response.find('[')
            end_idx = cleaned_response.rfind(']') + 1
            if start_idx != -1 and end_idx != -1:
                cleaned_response = cleaned_response[start_idx:end_idx]
            
            disbursements_data = json.loads(cleaned_response)
            if not isinstance(disbursements_data, list):
                disbursements_data = [disbursements_data]
            
            logger.info(f"Parsed {len(disbursements_data)} disbursements from LLM response")
            
            for item in disbursements_data:
                try:
                    # Map disbursement type to valid enum value
                    disbursement_type = item.get('disbursement_type', '')
                    mapped_disbursement_type = self._map_disbursement_type(disbursement_type)
                    item['disbursement_type'] = mapped_disbursement_type
                    
                    # Add required fields
                    item['case_id'] = self.current_case_id
                    
                    # Fix date format if needed
                    if 'date_incurred' in item:
                        item['date_incurred'] = self._fix_date_format(item['date_incurred'])
                    
                    # Ensure numeric fields are valid numbers with defaults
                    item['amount_net_gbp'] = float(item.get('amount_net_gbp', 0.0))
                    item['vat_gbp'] = float(item.get('vat_gbp', 0.0))
                    
                    # Calculate amount_gross_gbp if not provided
                    if 'amount_gross_gbp' not in item or item['amount_gross_gbp'] is None:
                        item['amount_gross_gbp'] = item['amount_net_gbp'] + item['vat_gbp']
                    else:
                        item['amount_gross_gbp'] = float(item['amount_gross_gbp'])
                    
                    # Ensure boolean field is properly set
                    item['is_recoverable'] = bool(item.get('is_recoverable', True))
                    
                    disbursement = Disbursement(**item)
                    disbursements.append(disbursement)
                    logger.info(f"Successfully created disbursement: {disbursement.description[:50]}...")
                except Exception as e:
                    logger.error(f"Error parsing Disbursement: {e} | Data: {item}")
                    continue
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing disbursements JSON: {e}")
            logger.error(f"Raw response: {disbursements_response}")
        
        logger.info(f"Entity extraction complete. Found {len(work_items)} work items and {len(disbursements)} disbursements")
        return work_items, disbursements

    def _map_activity_type(self, activity_type: str) -> str:
        """Map activity type to valid enum value."""
        activity_type = activity_type.lower()
        
        # Map common variations to valid enum values
        mapping = {
            'receipt of initial client instructions': 'Communications In (Letters/Emails)',
            'letter before action': 'Communications Out (Letters/Emails)',
            'defendant\'s response': 'Communications In (Letters/Emails)',
            'proceedings issued': 'Preparation',
            'defence filed': 'Review',
            'reply served': 'Drafting',
            'case management conference': 'Attendance at Court',
            'standard disclosure': 'Preparation',
            'witness statements': 'Preparation',
            'expert reports': 'Review',
            'trial bundle': 'Preparation',
            'trial': 'Attendance at Court',
            'judgment': 'Attendance at Court'
        }
        
        for key, value in mapping.items():
            if key in activity_type:
                return value
            
        # Default to Preparation if no match found
        return 'Preparation'

    def _map_disbursement_type(self, disbursement_type: str) -> str:
        """Map disbursement type to valid enum value."""
        disbursement_type = disbursement_type.lower()
        
        # Map common variations to valid enum values
        mapping = {
            'court fee': 'Court Fee',
            'counsel\'s fee': "Counsel's Fee",
            'expert\'s fee': "Expert's Fee",
            'travel': 'Travel Expense',
            'photocopying': 'Photocopying (External)',
            'process server': 'Process Server Fee',
            'miscellaneous': 'Other'
        }
        
        for key, value in mapping.items():
            if key in disbursement_type:
                return value
            
        # Default to Other if no match found
        return 'Other'

    def _fix_date_format(self, date_str: str) -> str:
        """Fix date format to YYYY-MM-DD."""
        try:
            # Handle date ranges by taking the first date
            if '-' in date_str and '/' in date_str:
                date_str = date_str.split('-')[0]
            
            # Parse and reformat the date
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            # If parsing fails, return today's date as fallback
            return datetime.now().strftime('%Y-%m-%d')
    
    def process_directory(self, directory_path: str, legal_case: Optional[LegalCase] = None, case_reference: Optional[str] = None) -> List[Dict[str, Any]]:
        """Process all documents in a directory and extract structured entities."""
        all_results = []
        with self.graph_ops as graph:
            for file_path in Path(directory_path).glob('*'):
                if file_path.suffix.lower() in ['.pdf', '.txt', '.md']:
                    try:
                        result = self.process_document(str(file_path), legal_case, case_reference)
                        all_results.append(result)
                    except Exception as e:
                        print(f"Error processing {file_path}: {str(e)}")
        return all_results

    def _extract_case_reference(self, content: str) -> str:
        """Extract case reference from document content."""
        # Common patterns for case references
        patterns = [
            r'Case No\.?\s*([A-Z0-9/-]+)',  # Case No. ABC123
            r'Reference:?\s*([A-Z0-9/-]+)',  # Reference: ABC123
            r'Claim No\.?\s*([A-Z0-9/-]+)',  # Claim No. ABC123
            r'File Ref\.?\s*([A-Z0-9/-]+)',  # File Ref. ABC123
            r'Our Ref\.?\s*([A-Z0-9/-]+)',   # Our Ref. ABC123
            r'Your Ref\.?\s*([A-Z0-9/-]+)',  # Your Ref. ABC123
            r'Claim Number:?\s*([A-Z0-9/-]+)' # Claim Number: ABC123
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If no reference found, generate a temporary one
        temp_ref = f"TEMP-{uuid.uuid4().hex[:8].upper()}"
        logger.warning(f"No case reference found in document, using temporary reference: {temp_ref}")
        return temp_ref 