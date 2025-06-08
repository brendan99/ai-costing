from typing import List, Optional, Dict, Any
from datetime import datetime
import os
from pathlib import Path

from ..models.domain import LegalCase, DocumentType, DocumentChunk
from ..llm.operations import LLMOperations
from ..graph.operations import Neo4jGraph

class DocumentGenerator:
    def __init__(self):
        self.llm_ops = LLMOperations()
        self.graph = Neo4jGraph()

    def generate_document(self, case_id: str, doc_type: DocumentType) -> str:
        """Generate a legal document using the RAG pipeline."""
        # 1. Get case data from Neo4j
        case = self.graph.get_case(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")

        # 2. Get relevant document chunks
        chunks = self._get_relevant_chunks(case, doc_type)

        # 3. Generate document using LLM
        return self.llm_ops.generate_document(case, doc_type)

    def _get_relevant_chunks(self, case: LegalCase, doc_type: DocumentType) -> List[DocumentChunk]:
        """Get relevant document chunks based on document type."""
        # Construct query based on document type
        if doc_type == DocumentType.BILL_OF_COSTS:
            query = f"Case {case.reference} work items, time spent, and amounts for Bill of Costs"
        elif doc_type == DocumentType.SCHEDULE_OF_COSTS:
            query = f"Case {case.reference} summary of costs and breakdown for Schedule of Costs"
        elif doc_type == DocumentType.POINTS_OF_DISPUTE:
            query = f"Case {case.reference} disputed items and amounts for Points of Dispute"
        else:  # Points of Reply
            query = f"Case {case.reference} responses to disputed items for Points of Reply"

        # Get embedding for query
        query_embedding = self.llm_ops.get_embedding(query)

        # Search for similar chunks
        return self.graph.search_similar_chunks(query_embedding, limit=5)

    def save_document(self, content: str, case: LegalCase, doc_type: DocumentType) -> str:
        """Save generated document to file."""
        # Create output directory if it doesn't exist
        output_dir = Path("output") / case.reference
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{doc_type.value.replace(' ', '_')}_{timestamp}.txt"
        file_path = output_dir / filename

        # Save document
        with open(file_path, "w") as f:
            f.write(content)

        return str(file_path) 