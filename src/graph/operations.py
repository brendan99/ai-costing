from typing import List, Optional, Dict, Any
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
import os
from dotenv import load_dotenv
from pathlib import Path
import sys
import uuid
from datetime import datetime
import logging
import json

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from src.models.domain import LegalCase, WorkItem, Disbursement, FeeEarner, DocumentChunk

load_dotenv()

logger = logging.getLogger(__name__)

class Neo4jGraph:
    def __init__(self):
        """Initialize Neo4j connection."""
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None
        self.connect()

    def connect(self):
        """Establish connection to Neo4j."""
        if not self.driver:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )

    def close(self):
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()
            self.driver = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def create_case(self, case: LegalCase) -> LegalCase:
        """Create a new case."""
        # Check if case already exists
        existing_case = self.find_case_by_reference(case.case_reference_number)
        if existing_case:
            return existing_case
            
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (c:Case {
                    id: $id,
                    case_name: $case_name,
                    case_reference_number: $case_reference_number,
                    our_firm_id: $our_firm_id,
                    our_client_party_id: $our_client_party_id,
                    date_opened: date($date_opened),
                    status: $status
                })
                RETURN c
                """,
                id=str(case.case_id),
                case_name=case.case_name,
                case_reference_number=case.case_reference_number,
                our_firm_id=str(case.our_firm_id),
                our_client_party_id=str(case.our_client_party_id),
                date_opened=case.date_opened.isoformat() if case.date_opened else None,
                status=case.status
            )
            created_case = result.single()[0]
            
            # Convert Neo4j DateTime to Python datetime
            case_data = dict(created_case)
            if case_data.get("date_opened"):
                case_data["date_opened"] = case_data["date_opened"].to_native()
            
            return LegalCase(**case_data)

    def create_work_item(self, case_id: str, work_item: WorkItem) -> str:
        """Create a new work item and link it to a case."""
        with self.driver.session() as session:
            result = session.execute_write(
                self._create_work_item_tx,
                case_id,
                work_item.model_dump()
            )
            return result

    @staticmethod
    def _create_work_item_tx(tx, case_id: str, work_item_data: Dict[str, Any]) -> str:
        # Convert UUID values to strings
        work_item_data = {k: str(v) if isinstance(v, uuid.UUID) else v for k, v in work_item_data.items()}
        
        query = """
        MATCH (c:Case {id: $case_id})
        CREATE (w:WorkItem {
            work_item_id: $work_item_id,
            case_id: $case_id,
            fee_earner_id: $fee_earner_id,
            date_of_work: date($date_of_work),
            activity_type: $activity_type,
            description: $description,
            time_spent_units: $time_spent_units,
            time_spent_decimal_hours: $time_spent_decimal_hours,
            applicable_hourly_rate_gbp: $applicable_hourly_rate_gbp,
            claimed_amount_gbp: $claimed_amount_gbp,
            is_recoverable: $is_recoverable,
            related_document_ids: $related_document_ids,
            source_reference: $source_reference,
            bill_item_number: $bill_item_number,
            disputed: $disputed,
            dispute_reason: $dispute_reason
        })
        CREATE (c)-[:HAS_WORK_ITEM]->(w)
        RETURN w.work_item_id
        """
        result = tx.run(query, {"case_id": case_id, **work_item_data})
        return result.single()[0]

    def create_fee_earner(self, case_id: str, fee_earner: FeeEarner) -> str:
        """Create a new fee earner and link it to a case."""
        with self.driver.session() as session:
            result = session.execute_write(
                self._create_fee_earner_tx,
                case_id,
                fee_earner.model_dump()
            )
            return result

    @staticmethod
    def _create_fee_earner_tx(tx, case_id: str, fee_earner_data: Dict[str, Any]) -> str:
        query = """
        MATCH (c:Case {id: $case_id})
        CREATE (f:FeeEarner {
            id: $id,
            name: $name,
            grade: $grade,
            hourly_rate: $hourly_rate
        })
        CREATE (c)-[:HAS_FEE_EARNER]->(f)
        RETURN f.id
        """
        result = tx.run(query, {"case_id": case_id, **fee_earner_data})
        return result.single()[0]

    def get_case(self, case_id: str) -> LegalCase:
        """Get a case by ID."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Case {id: $case_id})
                OPTIONAL MATCH (c)-[:HAS_WORK_ITEM]->(w:WorkItem)
                OPTIONAL MATCH (w)-[:PERFORMED_BY]->(f:FeeEarner)
                OPTIONAL MATCH (c)-[:HAS_DISBURSEMENT]->(d:Disbursement)
                RETURN c, collect(distinct w) as work_items, 
                       collect(distinct f) as fee_earners,
                       collect(distinct d) as disbursements
                """,
                case_id=case_id
            )
            record = result.single()
            if not record:
                return None
            
            case_node = record["c"]
            work_items = [w for w in record["work_items"] if w is not None]
            fee_earners = [f for f in record["fee_earners"] if f is not None]
            disbursements = [d for d in record["disbursements"] if d is not None]
            
            # Convert Neo4j DateTime to Python datetime
            case_data = dict(case_node)
            case_data["created_at"] = case_data["created_at"].to_native()
            case_data["updated_at"] = case_data["updated_at"].to_native()
            
            # Convert work item dates
            for work_item in work_items:
                work_item["date"] = work_item["date"].to_native()
            
            # Convert disbursement dates
            for disbursement in disbursements:
                disbursement["date"] = disbursement["date"].to_native()
            
            # Create Case model with converted dates
            return LegalCase(
                id=case_data["id"],
                title=case_data["title"],
                reference=case_data["reference"],
                court=case_data["court"],
                created_at=case_data["created_at"],
                updated_at=case_data["updated_at"],
                work_items=[WorkItem(**dict(w)) for w in work_items],
                fee_earners=[FeeEarner(**dict(f)) for f in fee_earners],
                disbursements=[Disbursement(**dict(d)) for d in disbursements]
            )

    def create_document_chunk(self, chunk: DocumentChunk, case: LegalCase):
        """Create a document chunk node and link it to its case."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (c:Case {id: $case_id})
                CREATE (d:DocumentChunk {
                    chunk_id: $chunk_id,
                    source_document_id: $source_document_id,
                    text_content: $text_content,
                    page_number_start: $page_number_start,
                    page_number_end: $page_number_end,
                    embedding: $embedding,
                    metadata: $metadata
                })
                CREATE (c)-[:HAS_DOCUMENT]->(d)
                """,
                case_id=str(case.case_id),
                chunk_id=str(chunk.chunk_id),
                source_document_id=str(chunk.source_document_id),
                text_content=chunk.text_content,
                page_number_start=chunk.page_number_start,
                page_number_end=chunk.page_number_end,
                embedding=json.dumps(chunk.embedding) if chunk.embedding is not None else None,
                metadata=json.dumps(chunk.metadata) if chunk.metadata else "{}"
            )

    def search_similar_chunks(self, embedding: List[float], limit: int = 5) -> List[DocumentChunk]:
        """Search for similar document chunks using vector similarity."""
        with self.driver.session() as session:
            result = session.execute_read(
                self._search_similar_chunks_tx,
                embedding,
                limit
            )
            return result

    @staticmethod
    def _search_similar_chunks_tx(tx, embedding: List[float], limit: int) -> List[DocumentChunk]:
        query = """
        CALL db.index.vector.queryNodes('document_chunks', $limit, $embedding)
        YIELD node, score
        MATCH (node)-[:HAS_DOCUMENT]->(c:Case)
        RETURN node, score, c.id as case_id
        ORDER BY score DESC
        """
        result = tx.run(query, embedding=embedding, limit=limit)
        chunks = []
        for record in result:
            chunk_data = dict(record["node"])
            # Convert JSON strings back to Python objects
            if chunk_data.get("embedding"):
                chunk_data["embedding"] = json.loads(chunk_data["embedding"])
            if chunk_data.get("metadata"):
                chunk_data["metadata"] = json.loads(chunk_data["metadata"])
            chunk_data["case_id"] = record["case_id"]
            chunks.append(DocumentChunk(**chunk_data))
        return chunks

    def document_exists(self, file_path: str) -> bool:
        """Check if a document has already been processed."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:DocumentChunk)
                WHERE c.source_file = $file_path
                RETURN count(c) as count
                """,
                file_path=file_path
            )
            return result.single()["count"] > 0

    def find_case_by_title(self, title: str) -> Optional[LegalCase]:
        """Find a case by its title."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Case)
                WHERE c.title = $title
                RETURN c
                """,
                title=title
            )
            record = result.single()
            if record:
                case_data = dict(record["c"])
                # Convert Neo4j DateTime to Python datetime
                case_data["created_at"] = case_data["created_at"].to_native()
                case_data["updated_at"] = case_data["updated_at"].to_native()
                return LegalCase(**case_data)
            return None

    def find_or_create_case(self, case: LegalCase) -> LegalCase:
        """Find an existing case by reference."""
        existing_case = self.find_case_by_reference(case.case_reference_number)
        if existing_case:
            return existing_case
        raise ValueError(f"No case found with reference: {case.case_reference_number}")

    def get_all_cases(self) -> List[LegalCase]:
        """Get all cases from the database."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Case)
                OPTIONAL MATCH (c)-[:HAS_WORK_ITEM]->(w:WorkItem)
                OPTIONAL MATCH (c)-[:HAS_FEE_EARNER]->(f:FeeEarner)
                OPTIONAL MATCH (c)-[:HAS_DISBURSEMENT]->(d:Disbursement)
                RETURN c, 
                       collect(DISTINCT w) as work_items,
                       collect(DISTINCT f) as fee_earners,
                       collect(DISTINCT d) as disbursements
                ORDER BY c.created_at DESC
            """)
            
            cases = []
            for record in result:
                case_data = dict(record["c"])
                # Convert Neo4j DateTime to Python datetime
                case_data["created_at"] = case_data["created_at"].to_native()
                case_data["updated_at"] = case_data["updated_at"].to_native()
                
                # Convert work items
                work_items = []
                for w in record["work_items"]:
                    if w:
                        item_data = dict(w)
                        item_data["date"] = item_data["date"].to_native()
                        work_items.append(item_data)
                case_data["work_items"] = work_items
                
                # Convert fee earners
                case_data["fee_earners"] = [dict(f) for f in record["fee_earners"] if f]
                
                # Convert disbursements
                disbursements = []
                for d in record["disbursements"]:
                    if d:
                        disb_data = dict(d)
                        disb_data["date"] = disb_data["date"].to_native()
                        disbursements.append(disb_data)
                case_data["disbursements"] = disbursements
                
                cases.append(LegalCase(**case_data))
            
            return cases

    def init_db(self):
        """Initialize database with required indexes and constraints."""
        try:
            # Create vector index for document chunks
            self.run_query("""
                CREATE VECTOR INDEX document_chunks_embedding IF NOT EXISTS
                FOR (c:DocumentChunk)
                ON (c.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
            """)
            logger.info("Created vector index for document chunks")
            
            # Create property indexes one by one
            self.run_query("CREATE INDEX case_id IF NOT EXISTS FOR (c:Case) ON (c.id)")
            self.run_query("CREATE INDEX document_id IF NOT EXISTS FOR (d:SourceDocument) ON (d.document_id)")
            self.run_query("CREATE INDEX chunk_id IF NOT EXISTS FOR (c:DocumentChunk) ON (c.chunk_id)")
            self.run_query("CREATE INDEX work_item_id IF NOT EXISTS FOR (w:WorkItem) ON (w.work_item_id)")
            self.run_query("CREATE INDEX disbursement_id IF NOT EXISTS FOR (d:Disbursement) ON (d.disbursement_id)")
            self.run_query("CREATE INDEX fee_earner_id IF NOT EXISTS FOR (f:FeeEarner) ON (f.fee_earner_id)")
            logger.info("Created property indexes")
            
            # Create constraints one by one with distinct names
            self.run_query("CREATE CONSTRAINT constraint_case_id IF NOT EXISTS FOR (c:Case) REQUIRE c.id IS UNIQUE")
            self.run_query("CREATE CONSTRAINT constraint_document_id IF NOT EXISTS FOR (d:SourceDocument) REQUIRE d.document_id IS UNIQUE")
            self.run_query("CREATE CONSTRAINT constraint_chunk_id IF NOT EXISTS FOR (c:DocumentChunk) REQUIRE c.chunk_id IS UNIQUE")
            self.run_query("CREATE CONSTRAINT constraint_work_item_id IF NOT EXISTS FOR (w:WorkItem) REQUIRE w.work_item_id IS UNIQUE")
            self.run_query("CREATE CONSTRAINT constraint_disbursement_id IF NOT EXISTS FOR (d:Disbursement) REQUIRE d.disbursement_id IS UNIQUE")
            self.run_query("CREATE CONSTRAINT constraint_fee_earner_id IF NOT EXISTS FOR (f:FeeEarner) REQUIRE f.fee_earner_id IS UNIQUE")
            logger.info("Created constraints")
            
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise

    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            try:
                record = result.single()
                return record[0] if record else None
            except Exception:
                # For schema operations (CREATE INDEX, etc.), just return None
                return None

    def store_case(self, case):
        """Store a LegalCase object in Neo4j."""
        # Check if case already exists
        existing_case = self.find_case_by_reference(case.case_reference_number)
        if existing_case:
            return existing_case
            
        with self.driver.session() as session:
            session.run("""
                MERGE (c:Case {
                    id: $id,
                    reference: $reference,
                    our_firm_id: $our_firm_id,
                    our_client_party_id: $our_client_party_id
                })
            """, {
                "id": str(case.case_id),
                "reference": case.case_reference_number,
                "our_firm_id": str(case.our_firm_id),
                "our_client_party_id": str(case.our_client_party_id)
            })

    def store_document(self, document):
        """Store a SourceDocument object in Neo4j and link it to its case."""
        with self.driver.session() as session:
            session.run(
                '''
                MATCH (c:Case {id: $case_id})
                MERGE (d:SourceDocument {
                    document_id: $document_id
                })
                SET d.case_id = $case_id,
                    d.file_name = $file_name,
                    d.file_path = $file_path,
                    d.document_type = $document_type,
                    d.date_created = $date_created,
                    d.date_received = $date_received,
                    d.author = $author,
                    d.recipient = $recipient,
                    d.extracted_text_path = $extracted_text_path,
                    d.metadata = $metadata
                MERGE (c)-[:HAS_DOCUMENT]->(d)
                ''', {
                    "document_id": str(document.document_id),
                    "case_id": str(document.case_id),
                    "file_name": document.file_name,
                    "file_path": document.file_path,
                    "document_type": document.document_type.value if hasattr(document.document_type, 'value') else str(document.document_type),
                    "date_created": document.date_created.isoformat() if document.date_created else None,
                    "date_received": document.date_received.isoformat() if document.date_received else None,
                    "author": document.author,
                    "recipient": document.recipient,
                    "extracted_text_path": document.extracted_text_path,
                    "metadata": json.dumps(document.metadata) if hasattr(document, 'metadata') else "{}",
                }
            )

    def create_disbursement(self, case_id: str, disbursement: Disbursement) -> str:
        """Create a new disbursement and link it to a case."""
        with self.driver.session() as session:
            result = session.execute_write(
                self._create_disbursement_tx,
                case_id,
                disbursement.model_dump()
            )
            return result

    @staticmethod
    def _create_disbursement_tx(tx, case_id: str, disbursement_data: Dict[str, Any]) -> str:
        # Convert UUID values to strings
        disbursement_data = {k: str(v) if isinstance(v, uuid.UUID) else v for k, v in disbursement_data.items()}
        
        query = """
        MATCH (c:Case {id: $case_id})
        CREATE (d:Disbursement {
            disbursement_id: $disbursement_id,
            case_id: $case_id,
            date_incurred: date($date_incurred),
            disbursement_type: $disbursement_type,
            description: $description,
            payee_name: $payee_name,
            amount_net_gbp: $amount_net_gbp,
            vat_gbp: $vat_gbp,
            amount_gross_gbp: $amount_gross_gbp,
            is_recoverable: $is_recoverable,
            voucher_document_id: $voucher_document_id,
            bill_item_number: $bill_item_number,
            disputed: $disputed,
            dispute_reason: $dispute_reason
        })
        CREATE (c)-[:HAS_DISBURSEMENT]->(d)
        RETURN d.disbursement_id
        """
        result = tx.run(query, {"case_id": case_id, **disbursement_data})
        return result.single()[0]

    def find_case_by_reference(self, reference: str) -> Optional[LegalCase]:
        """Find a case by its reference number."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Case)
                WHERE c.reference = $reference
                RETURN c
                """,
                reference=reference
            )
            record = result.single()
            if record:
                case_data = dict(record["c"])
                # Convert Neo4j DateTime to Python datetime
                case_data["created_at"] = case_data["created_at"].to_native()
                case_data["updated_at"] = case_data["updated_at"].to_native()
                return LegalCase(**case_data)
            return None 