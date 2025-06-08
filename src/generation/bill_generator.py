import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import jinja2
import uuid
from ..models.domain import (
    LegalCase, WorkItem, Disbursement, FeeEarner,
    Bill, BillSection, BillItem
)
from ..llm.operations import LLMOperations
from ..graph.operations import Neo4jGraph

logger = logging.getLogger(__name__)

class BillGenerator:
    def __init__(self, graph_ops: Neo4jGraph):
        """Initialize bill generator with graph operations."""
        self.graph_ops = graph_ops
        self.llm_ops = LLMOperations()
        self.template_loader = jinja2.FileSystemLoader(searchpath="./templates")
        self.template_env = jinja2.Environment(loader=self.template_loader)
        logger.info("BillGenerator initialized")
        
    def generate_bill(self, case_id: Optional[str] = None) -> Bill:
        """Generate a bill of costs for a case."""
        try:
            logger.info(f"Starting bill generation for case: {case_id}")
            
            # Get case data
            if case_id:
                case = self.graph_ops.get_case(case_id)
            else:
                # Get the most recent case
                cases = self.graph_ops.get_all_cases()
                if not cases:
                    raise ValueError("No cases found in database")
                case = cases[0]
            
            logger.info(f"Generating bill for case: {case.case_name}")
            
            # Get work items and disbursements
            work_items = self.graph_ops.get_work_items(case.case_id)
            disbursements = self.graph_ops.get_disbursements(case.case_id)
            
            logger.info(f"Found {len(work_items)} work items and {len(disbursements)} disbursements")
            
            # Create bill sections
            sections = []
            
            # Work items section
            if work_items:
                work_items_section = BillSection(
                    section_id=str(uuid.uuid4()),
                    title="Work Done",
                    items=[
                        BillItem(
                            item_id=str(uuid.uuid4()),
                            date=item.date_of_work,
                            description=item.description,
                            amount=item.claimed_amount_gbp,
                            is_recoverable=item.is_recoverable
                        )
                        for item in sorted(work_items, key=lambda x: x.date_of_work)
                    ]
                )
                sections.append(work_items_section)
                logger.info(f"Created work items section with {len(work_items_section.items)} items")
            
            # Disbursements section
            if disbursements:
                disbursements_section = BillSection(
                    section_id=str(uuid.uuid4()),
                    title="Disbursements",
                    items=[
                        BillItem(
                            item_id=str(uuid.uuid4()),
                            date=item.date_incurred,
                            description=item.description,
                            amount=item.amount_gross_gbp,
                            is_recoverable=item.is_recoverable
                        )
                        for item in sorted(disbursements, key=lambda x: x.date_incurred)
                    ]
                )
                sections.append(disbursements_section)
                logger.info(f"Created disbursements section with {len(disbursements_section.items)} items")
            
            # Calculate totals
            total_amount = sum(
                sum(item.amount for item in section.items)
                for section in sections
            )
            
            recoverable_amount = sum(
                sum(item.amount for item in section.items if item.is_recoverable)
                for section in sections
            )
            
            # Create bill
            bill = Bill(
                bill_id=str(uuid.uuid4()),
                case_id=case.case_id,
                case_name=case.case_name,
                date_generated=datetime.now(),
                sections=sections,
                total_amount=total_amount,
                recoverable_amount=recoverable_amount
            )
            
            logger.info(f"Bill generated successfully. Total amount: £{total_amount:.2f}, Recoverable: £{recoverable_amount:.2f}")
            return bill
            
        except Exception as e:
            logger.error(f"Error generating bill: {str(e)}", exc_info=True)
            raise
    
    def _get_relevant_chunks(self, case: LegalCase) -> List[Dict[str, Any]]:
        """Get relevant document chunks for bill generation context."""
        query = f"Case {case.reference} work items, time spent, and amounts for Bill of Costs"
        query_embedding = self.llm_ops.get_embedding(query)
        return self.graph_ops.search_similar_chunks(query_embedding, limit=5)
    
    def _group_work_items_by_grade(self, work_items: List[WorkItem]) -> Dict[str, List[WorkItem]]:
        """Group work items by fee earner grade."""
        grouped = {}
        for item in work_items:
            grade = item.fee_earner.grade
            if grade not in grouped:
                grouped[grade] = []
            grouped[grade].append(item)
        return grouped
    
    def _calculate_totals(self, case: LegalCase) -> Dict[str, float]:
        """Calculate totals for the bill."""
        profit_costs = sum(item.amount for item in case.work_items)
        disbursements = sum(d.amount for d in case.disbursements)
        vat_profit = profit_costs * 0.20  # 20% VAT
        vat_disbursements = sum(d.amount * 0.20 for d in case.disbursements if d.vat_applicable)
        
        return {
            "profit_costs": profit_costs,
            "disbursements": disbursements,
            "vat_profit": vat_profit,
            "vat_disbursements": vat_disbursements,
            "total": profit_costs + disbursements + vat_profit + vat_disbursements
        }
    
    def save_bill(self, content: str, case: LegalCase) -> Path:
        """Save the generated bill to a file."""
        output_dir = Path("output/bills")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = output_dir / f"bill_of_costs_{case.reference}_{datetime.now().strftime('%Y%m%d')}.html"
        with open(file_path, "w") as f:
            f.write(content)
        
        return file_path 