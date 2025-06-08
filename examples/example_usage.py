#!/usr/bin/env python3
"""
Example usage of the AI Costing Graph system.

This script demonstrates how to:
1. Ingest case documents
2. Generate a Bill of Costs
3. Generate Points of Dispute
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import uuid
from decimal import Decimal

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from src.models.domain import LegalCase, WorkItem, FeeEarner, DocumentType
from src.graph.operations import Neo4jGraph
from src.document.processor import DocumentProcessor
from src.generation.generator import DocumentGenerator

def create_sample_case():
    """Create a sample case with some work items and fee earners."""
    case_id = str(uuid.uuid4())
    
    # Create fee earners
    partner = FeeEarner(
        id=str(uuid.uuid4()),
        name="John Smith",
        grade="Partner",
        hourly_rate=Decimal("350.00")
    )
    
    associate = FeeEarner(
        id=str(uuid.uuid4()),
        name="Jane Doe",
        grade="Associate",
        hourly_rate=Decimal("250.00")
    )
    
    # Create work items
    work_items = [
        WorkItem(
            id=str(uuid.uuid4()),
            date=datetime(2024, 1, 15),
            description="Initial client meeting",
            time_spent_units=10,
            fee_earner_id=partner.id,
            amount=Decimal("350.00"),
            category="Pre-action"
        ),
        WorkItem(
            id=str(uuid.uuid4()),
            date=datetime(2024, 1, 20),
            description="Drafting letter before action",
            time_spent_units=15,
            fee_earner_id=associate.id,
            amount=Decimal("375.00"),
            category="Pre-action"
        ),
        WorkItem(
            id=str(uuid.uuid4()),
            date=datetime(2024, 2, 1),
            description="Preparing claim form",
            time_spent_units=20,
            fee_earner_id=associate.id,
            amount=Decimal("500.00"),
            category="Proceedings"
        )
    ]
    
    return LegalCase(
        id=case_id,
        reference="EXAMPLE001",
        title="Smith v Jones",
        court="High Court",
        description="Commercial dispute regarding breach of contract",
        work_items=work_items,
        fee_earners=[partner, associate],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

def main():
    """Run the example."""
    try:
        # Initialize components
        graph = Neo4jGraph()
        graph.connect()
        processor = DocumentProcessor()
        generator = DocumentGenerator()
        
        # Create and store sample case
        case = create_sample_case()
        case_id = graph.create_case(case)
        print(f"Created case: {case.reference}")
        
        # Store fee earners
        for fee_earner in case.fee_earners:
            graph.create_fee_earner(case.id, fee_earner)
        
        # Store work items
        for work_item in case.work_items:
            graph.create_work_item(case.id, work_item)
        
        # Generate Bill of Costs
        print("\nGenerating Bill of Costs...")
        bill_of_costs = generator.generate_document(case.id, DocumentType.BILL_OF_COSTS)
        bill_path = generator.save_document(bill_of_costs, case, DocumentType.BILL_OF_COSTS)
        print(f"Bill of Costs saved to: {bill_path}")
        
        # Generate Points of Dispute
        print("\nGenerating Points of Dispute...")
        points_of_dispute = generator.generate_document(case.id, DocumentType.POINTS_OF_DISPUTE)
        points_path = generator.save_document(points_of_dispute, case, DocumentType.POINTS_OF_DISPUTE)
        print(f"Points of Dispute saved to: {points_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        graph.close()

if __name__ == "__main__":
    main() 