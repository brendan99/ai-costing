from typing import List, Optional, Dict, Any
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
import os
from dotenv import load_dotenv
from pathlib import Path
import sys
import uuid
from datetime import datetime

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from src.models.domain import Case, WorkItem, Disbursement, FeeEarner, DocumentChunk

load_dotenv()

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

    def create_case(self, case: Case) -> Case:
        """Create a new case."""
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (c:Case {
                    id: $id,
                    title: $title,
                    reference: $reference,
                    court: $court,
                    created_at: datetime($created_at),
                    updated_at: datetime($updated_at)
                })
                RETURN c
                """,
                id=case.id,
                title=case.title,
                reference=case.reference,
                court=case.court,
                created_at=case.created_at.isoformat(),
                updated_at=case.updated_at.isoformat()
            )
            created_case = result.single()[0]
            
            # Convert Neo4j DateTime to Python datetime
            case_data = dict(created_case)
            case_data["created_at"] = case_data["created_at"].to_native()
            case_data["updated_at"] = case_data["updated_at"].to_native()
            
            return Case(**case_data)

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
        query = """
        MATCH (c:Case {id: $case_id})
        CREATE (w:WorkItem {
            id: $id,
            date: datetime($date),
            description: $description,
            time_spent_units: $time_spent_units,
            fee_earner_id: $fee_earner_id,
            amount: $amount,
            category: $category
        })
        CREATE (c)-[:HAS_WORK_ITEM]->(w)
        RETURN w.id
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

    def get_case(self, case_id: str) -> Case:
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
            return Case(
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

    def create_document_chunk(self, chunk: DocumentChunk, case: Case):
        """Create a document chunk node and link it to its case."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (c:Case {id: $case_id})
                CREATE (d:DocumentChunk {
                    id: $id,
                    content: $content,
                    source_file: $source_file,
                    page_number: $page_number,
                    chunk_index: $chunk_index,
                    created_at: $created_at
                })
                CREATE (c)-[:HAS_DOCUMENT]->(d)
                """,
                case_id=case.id,
                id=chunk.id,
                content=chunk.content,
                source_file=chunk.source_file,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                created_at=chunk.created_at
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
        MATCH (node)-[:HAS_DOCUMENT_CHUNK]->(c:Case)
        RETURN node, score, c.id as case_id
        ORDER BY score DESC
        """
        result = tx.run(query, embedding=embedding, limit=limit)
        chunks = []
        for record in result:
            chunk_data = dict(record["node"])
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

    def find_case_by_title(self, title: str) -> Optional[Case]:
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
                return Case(**case_data)
            return None

    def find_or_create_case(self, case: Case) -> Case:
        """Find an existing case by title or create a new one."""
        existing_case = self.find_case_by_title(case.title)
        if existing_case:
            return existing_case
        
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (c:Case {
                    id: $id,
                    reference: $reference,
                    title: $title,
                    court: $court,
                    description: $description,
                    created_at: datetime($created_at),
                    updated_at: datetime($updated_at)
                })
                RETURN c
                """,
                id=case.id,
                reference=case.reference,
                title=case.title,
                court=case.court,
                description=case.description,
                created_at=case.created_at.isoformat(),
                updated_at=case.updated_at.isoformat()
            )
            created_case = result.single()[0]
            
            # Convert Neo4j DateTime to Python datetime
            case_data = dict(created_case)
            case_data["created_at"] = case_data["created_at"].to_native()
            case_data["updated_at"] = case_data["updated_at"].to_native()
            
            return Case(**case_data)

    def get_all_cases(self) -> List[Case]:
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
                
                cases.append(Case(**case_data))
            
            return cases 