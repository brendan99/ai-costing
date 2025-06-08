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
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
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
                MERGE (c:Case {case_id: $case_id})
                ON CREATE SET
                    c.case_name = $case_name,
                    c.case_reference_number = $case_reference_number,
                    c.our_firm_id = $our_firm_id,
                    c.our_client_party_id = $our_client_party_id,
                    c.date_opened = date($date_opened),
                    c.status = $status
                RETURN c
                """,
                case_id=str(case.case_id),
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
        MATCH (c:Case {case_id: $case_id})
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
        MATCH (c:Case {case_id: $case_id})
        CREATE (f:FeeEarner {
            fee_earner_id: $fee_earner_id,
            name: $name,
            grade: $grade,
            hourly_rate: $hourly_rate
        })
        CREATE (c)-[:HAS_FEE_EARNER]->(f)
        RETURN f.fee_earner_id
        """
        result = tx.run(query, {"case_id": case_id, **fee_earner_data})
        return result.single()[0]

    def get_case(self, case_id: str) -> LegalCase:
        """Get a case by ID."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Case {case_id: $case_id})
                OPTIONAL MATCH (c)-[:HAS_WORK_ITEM]->(w:WorkItem)
                OPTIONAL MATCH (w)-[:PERFORMED_BY]->(f:FeeEarner)
                OPTIONAL MATCH (c)-[:HAS_DISBURSEMENT]->(d:Disbursement)
                RETURN c, collect(distinct w) as work_items, 
                       collect(distinct f) as fee_earners,
                       collect(distinct d) as disbursements
                """,
                case_id=str(case_id)
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
                case_id=case_data["case_id"],
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
                MATCH (c:Case {case_id: $case_id})
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
        RETURN node, score, c.case_id as case_id
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

    def _run_schema_query(self, query, parameters=None):
        """Run a Cypher schema query and return the result object directly."""
        with self.driver.session(database=self.database) as session:
            return session.run(query, parameters or {})

    def init_db(self):
        """Initialize the database with required indexes and constraints."""
        import traceback
        try:
            # Drop existing constraints and indexes using a direct session
            with self.driver.session(database=self.database) as session:
                # First drop constraints
                result = session.run("SHOW CONSTRAINTS")
                constraints = [record.data() for record in result]
                constraint_names = [data.get('name') for data in constraints if data.get('name')]
                logger.debug(f"Found constraints: {constraint_names}")
                for name in constraint_names:
                    session.run(f"DROP CONSTRAINT {name} IF EXISTS")
                
                # Then drop indexes
                result = session.run("SHOW INDEXES")
                indexes = [record.data() for record in result]
                index_names = [data.get('name') for data in indexes if data.get('name')]
                logger.debug(f"Found indexes: {index_names}")
                for name in index_names:
                    session.run(f"DROP INDEX {name} IF EXISTS")
            
            # Create constraints (which will automatically create indexes)
            self.run_query("CREATE CONSTRAINT constraint_chunk_id IF NOT EXISTS FOR (c:DocumentChunk) REQUIRE c.chunk_id IS UNIQUE")
            self.run_query("CREATE CONSTRAINT constraint_case_id IF NOT EXISTS FOR (c:Case) REQUIRE c.case_id IS UNIQUE")
            self.run_query("CREATE CONSTRAINT constraint_document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE")
            self.run_query("CREATE CONSTRAINT constraint_work_item_id IF NOT EXISTS FOR (w:WorkItem) REQUIRE w.work_item_id IS UNIQUE")
            self.run_query("CREATE CONSTRAINT constraint_disbursement_id IF NOT EXISTS FOR (d:Disbursement) REQUIRE d.disbursement_id IS UNIQUE")
            self.run_query("CREATE CONSTRAINT constraint_fee_earner_id IF NOT EXISTS FOR (f:FeeEarner) REQUIRE f.fee_earner_id IS UNIQUE")
            
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def run_query(self, query, parameters=None):
        """Run a Cypher query and return the result object."""
        with self.driver.session(database=self.database) as session:
            return session.run(query, parameters or {})

    def store_case(self, case):
        """Store a LegalCase object in Neo4j."""
        # Check if case already exists
        existing_case = self.find_case_by_reference(case.case_reference_number)
        if existing_case:
            logger.info(f"Case already exists with reference {case.case_reference_number}")
            return existing_case
            
        with self.driver.session() as session:
            # Log the case data being stored
            logger.info(f"Storing new case with ID: {case.case_id}")
            logger.info(f"Case data: {case.model_dump()}")
            
            # Convert data types for Neo4j compatibility
            params = {
                "case_id": str(case.case_id),  # Neo4j doesn't support UUID type
                "case_name": case.case_name,
                "case_type": case.case_type.value if hasattr(case.case_type, 'value') else str(case.case_type),
                "status": case.status.value if hasattr(case.status, 'value') else str(case.status),
                "created_at": case.created_at.isoformat(),  # Convert to ISO format string for datetime()
                "updated_at": case.updated_at.isoformat(),  # Convert to ISO format string for datetime()
                "case_reference_number": case.case_reference_number,
                "our_firm_id": str(case.our_firm_id) if case.our_firm_id else None,
                "our_client_party_id": str(case.our_client_party_id) if case.our_client_party_id else None,
                "date_opened": case.date_opened.isoformat() if case.date_opened else None  # Convert to ISO format string for date()
            }
            
            session.run(
                """
                MERGE (c:Case {case_id: $case_id})
                ON CREATE SET
                    c.case_id = $case_id,
                    c.case_name = $case_name,
                    c.case_type = $case_type,
                    c.status = $status,
                    c.created_at = datetime($created_at),
                    c.updated_at = datetime($updated_at),
                    c.case_reference_number = $case_reference_number,
                    c.our_firm_id = $our_firm_id,
                    c.our_client_party_id = $our_client_party_id,
                    c.date_opened = CASE WHEN $date_opened IS NOT NULL THEN date($date_opened) ELSE null END
                """,
                params
            )
            
            # Verify the case was created
            verify = session.run(
                "MATCH (c:Case {case_id: $case_id}) RETURN c",
                {"case_id": str(case.case_id)}
            )
            if not verify.single():
                raise ValueError(f"Failed to create case with ID {case.case_id}")
            
            logger.info(f"Successfully created case with ID: {case.case_id}")
            return case

    def store_document(self, document):
        """Store a SourceDocument object in Neo4j and link it to its case."""
        with self.driver.session() as session:
            session.run(
                '''
                MATCH (c:Case {case_id: $case_id})
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

    def _create_disbursement_tx(self, tx, case_id: str, disbursement_data: Dict[str, Any]) -> str:
        """Transaction method for creating a disbursement."""
        try:
            # Log the incoming data
            logger.info(f"Creating disbursement for case {case_id}")
            logger.debug(f"Disbursement data: {json.dumps(disbursement_data, default=str)}")
            
            # Convert data types for Neo4j compatibility
            params = {
                "case_id": str(case_id),  # Neo4j doesn't support UUID type
                "disbursement_id": str(disbursement_data['disbursement_id']),  # Neo4j doesn't support UUID type
                "date_incurred": disbursement_data['date_incurred'].isoformat(),  # Convert to ISO format string for date()
                "disbursement_type": disbursement_data['disbursement_type'].value if hasattr(disbursement_data['disbursement_type'], 'value') else str(disbursement_data['disbursement_type']),
                "status": disbursement_data['status'].value if hasattr(disbursement_data['status'], 'value') else str(disbursement_data['status']),
                "description": disbursement_data['description'],
                "payee_name": disbursement_data.get('payee_name'),
                "amount_net_gbp": float(disbursement_data['amount_net_gbp']),  # Ensure float for numeric values
                "vat_gbp": float(disbursement_data['vat_gbp']),  # Ensure float for numeric values
                "amount_gross_gbp": float(disbursement_data.get('amount_gross_gbp', disbursement_data['amount_net_gbp'] + disbursement_data['vat_gbp'])),  # Calculate if not provided
                "is_recoverable": bool(disbursement_data['is_recoverable']),  # Ensure boolean
                "voucher_document_id": str(disbursement_data['voucher_document_id']) if disbursement_data.get('voucher_document_id') else None,
                "bill_item_number": disbursement_data.get('bill_item_number'),
                "disputed": bool(disbursement_data.get('disputed', False)),  # Ensure boolean with default
                "dispute_reason": disbursement_data.get('dispute_reason')
            }
            
            logger.debug(f"Converted parameters: {json.dumps(params, default=str)}")
            
            # First check if case exists and log the result
            case_check = tx.run(
                "MATCH (c:Case) WHERE c.case_id = $case_id RETURN c.case_id",
                {"case_id": params["case_id"]}
            )
            case = case_check.single()
            
            if not case:
                # Log all available cases for debugging
                all_cases = tx.run("MATCH (c:Case) RETURN c.case_id, c.case_name").data()
                logger.error(f"Case not found with ID: {params['case_id']}")
                logger.error(f"Available cases: {json.dumps(all_cases, default=str)}")
                raise ValueError(f"Case not found with ID: {params['case_id']}")
            
            logger.info(f"Found case {params['case_id']}, proceeding with disbursement creation")
            
            # Check if disbursement already exists
            existing_disbursement = tx.run(
                "MATCH (d:Disbursement {disbursement_id: $disbursement_id}) RETURN d.disbursement_id",
                {"disbursement_id": params["disbursement_id"]}
            ).single()
            if existing_disbursement:
                logger.warning(f"Disbursement with ID {params['disbursement_id']} already exists. Skipping creation.")
                return existing_disbursement["disbursement_id"]
            
            # Create the disbursement with explicit RETURN clause
            result = tx.run(
                """
                MATCH (c:Case {case_id: $case_id})
                CREATE (d:Disbursement {
                    disbursement_id: $disbursement_id,
                    case_id: $case_id,
                    date_incurred: date($date_incurred),
                    disbursement_type: $disbursement_type,
                    status: $status,
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
                RETURN d.disbursement_id as disbursement_id
                """,
                params
            )
            
            # Get the result and verify it
            record = result.single()
            if not record:
                logger.error("Failed to create disbursement - no record returned")
                logger.error(f"Query parameters: {json.dumps(params, default=str)}")
                raise ValueError("Failed to create disbursement - no record returned")
            
            disbursement_id = record.get('disbursement_id')
            if not disbursement_id:
                logger.error("Failed to create disbursement - no ID in returned record")
                logger.error(f"Returned record: {record}")
                raise ValueError("Failed to create disbursement - no ID in returned record")
            
            logger.info(f"Successfully created disbursement with ID: {disbursement_id}")
            return disbursement_id
            
        except Exception as e:
            logger.error(f"Error creating disbursement: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Disbursement data: {json.dumps(disbursement_data, default=str)}")
            if 'params' in locals():
                logger.error(f"Converted parameters: {json.dumps(params, default=str)}")
            raise

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

    def check_db_state(self):
        """Check the current state of the database including indexes, constraints and node counts."""
        try:
            with self.driver.session() as session:
                # Get indexes
                indexes = []
                result = session.run("SHOW INDEXES")
                for record in result:
                    indexes.append(dict(record))
                print("\nIndexes:")
                for idx in indexes:
                    print(f"- {idx}")
                
                # Get constraints
                constraints = []
                result = session.run("SHOW CONSTRAINTS")
                for record in result:
                    constraints.append(dict(record))
                print("\nConstraints:")
                for constraint in constraints:
                    print(f"- {constraint}")
                
                # Get node counts
                node_counts = []
                result = session.run("MATCH (n) RETURN labels(n) as label, count(*) as count")
                for record in result:
                    node_counts.append(dict(record))
                print("\nNode Counts:")
                for count in node_counts:
                    print(f"- {count}")
                
                # Get relationships
                relationships = []
                result = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(*) as count")
                for record in result:
                    relationships.append(dict(record))
                print("\nRelationships:")
                for rel in relationships:
                    print(f"- {rel}")
                
                return {
                    "indexes": indexes,
                    "constraints": constraints,
                    "node_counts": node_counts,
                    "relationships": relationships
                }
        except Exception as e:
            logger.error(f"Error checking database state: {str(e)}")
            raise 