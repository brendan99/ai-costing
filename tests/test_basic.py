import pytest
from datetime import datetime
from decimal import Decimal
import uuid

from src.models.domain import Case, WorkItem, FeeEarner, DocumentType
from src.graph.operations import Neo4jGraph
from src.llm.operations import LLMOperations
from src.document.processor import DocumentProcessor
from src.generation.generator import DocumentGenerator

@pytest.fixture
def test_case():
    """Create a test case with some work items and fee earners."""
    case_id = str(uuid.uuid4())
    fee_earner = FeeEarner(
        id=str(uuid.uuid4()),
        name="John Smith",
        grade="Partner",
        hourly_rate=Decimal("350.00")
    )
    
    work_item = WorkItem(
        id=str(uuid.uuid4()),
        date=datetime.now(),
        description="Initial client meeting",
        time_spent_units=10,
        fee_earner_id=fee_earner.id,
        amount=Decimal("350.00"),
        category="Pre-action"
    )
    
    return Case(
        id=case_id,
        reference="TEST001",
        title="Test Case",
        court="High Court",
        description="A test case for unit testing",
        work_items=[work_item],
        fee_earners=[fee_earner],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

def test_case_model(test_case):
    """Test that the Case model works correctly."""
    assert test_case.reference == "TEST001"
    assert len(test_case.work_items) == 1
    assert len(test_case.fee_earners) == 1
    assert test_case.work_items[0].amount == Decimal("350.00")
    assert test_case.fee_earners[0].name == "John Smith"

def test_llm_operations():
    """Test that LLM operations can be initialized."""
    llm_ops = LLMOperations()
    assert llm_ops.model == "mistral"
    assert llm_ops.embedding_model == "nomic-embed-text"

def test_document_processor():
    """Test that DocumentProcessor can be initialized."""
    processor = DocumentProcessor()
    assert processor.text_splitter.chunk_size == 1000
    assert processor.text_splitter.chunk_overlap == 150

def test_document_generator():
    """Test that DocumentGenerator can be initialized."""
    generator = DocumentGenerator()
    assert generator is not None 