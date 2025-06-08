import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import jinja2
import uuid
import re
import os
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
                # Convert string UUID to UUID object if needed
                if isinstance(case_id, str):
                    try:
                        case_id = uuid.UUID(case_id)
                    except ValueError:
                        raise ValueError(f"Invalid UUID format: {case_id}")
                case = self.graph_ops.get_case(str(case_id))
            else:
                # Get the most recent case
                cases = self.graph_ops.get_all_cases()
                if not cases:
                    raise ValueError("No cases found in database")
                case = cases[0]
            
            if not case:
                raise ValueError(f"No case found with ID: {case_id}")
            
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
                            time_spent_units=item.time_spent_units,
                            time_spent_decimal_hours=item.time_spent_decimal_hours,
                            hourly_rate_gbp=item.applicable_hourly_rate_gbp,
                            amount=item.claimed_amount_gbp or (item.time_spent_decimal_hours * item.applicable_hourly_rate_gbp),
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
                            description=f"{item.description} ({item.disbursement_type.value})",
                            amount=item.amount_gross_gbp or (item.amount_net_gbp + item.vat_gbp),
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
                bill_id=uuid.uuid4(),
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
    
    def generate_bill_html(self, bill: Bill) -> str:
        """Generate HTML content for the bill using the template."""
        try:
            # Get case details
            case = self.graph_ops.get_case(str(bill.case_id))
            if not case:
                raise ValueError(f"Case not found for bill {bill.bill_id}")

            # Group work items by fee earner grade
            work_items_by_grade = {}
            for section in bill.sections:
                if section.title == "Work Done":
                    for item in section.items:
                        # Extract hourly rate from description if available
                        rate_match = re.search(r'@ £(\d+\.?\d*)/hr', item.description)
                        hourly_rate = float(rate_match.group(1)) if rate_match else 0.0
                        
                        # Determine grade based on hourly rate
                        grade = self._get_fee_earner_grade(hourly_rate)
                        
                        if grade not in work_items_by_grade:
                            work_items_by_grade[grade] = []
                        work_items_by_grade[grade].append(item)

            # Group disbursements by type
            disbursements_by_type = {}
            for section in bill.sections:
                if section.title == "Disbursements":
                    for item in section.items:
                        # Extract disbursement type from description
                        disbursement_type = "Other"  # Default type
                        if "court fee" in item.description.lower():
                            disbursement_type = "Court Fee"
                        elif "counsel" in item.description.lower():
                            disbursement_type = "Counsel's Fee"
                        elif "expert" in item.description.lower():
                            disbursement_type = "Expert's Fee"
                        elif "travel" in item.description.lower():
                            disbursement_type = "Travel Expense"
                        elif "photocopy" in item.description.lower():
                            disbursement_type = "Photocopying"
                        
                        if disbursement_type not in disbursements_by_type:
                            disbursements_by_type[disbursement_type] = []
                        disbursements_by_type[disbursement_type].append(item)

            # Calculate totals
            profit_costs = sum(item.amount for section in bill.sections if section.title == "Work Done" for item in section.items)
            disbursements = sum(item.amount for section in bill.sections if section.title == "Disbursements" for item in section.items)
            vat_on_profit_costs = profit_costs * 0.20  # 20% VAT
            vat_on_disbursements = disbursements * 0.20  # 20% VAT
            grand_total = profit_costs + disbursements + vat_on_profit_costs + vat_on_disbursements

            # Load and render template
            template = self.template_env.get_template("bill_of_costs.html")
            html_content = template.render(
                case=case,
                work_items_by_grade=work_items_by_grade,
                disbursements_by_type=disbursements_by_type,
                profit_costs=profit_costs,
                disbursements=disbursements,
                vat_on_profit_costs=vat_on_profit_costs,
                vat_on_disbursements=vat_on_disbursements,
                grand_total=grand_total,
                generated_date=datetime.now().strftime("%d.%m.%Y")
            )
            return html_content
        except Exception as e:
            logger.error(f"Error generating HTML bill: {str(e)}")
            raise
    
    def _get_fee_earner_grade(self, hourly_rate: float) -> str:
        """Determine fee earner grade based on hourly rate."""
        if hourly_rate >= 500:
            return "Grade A"
        elif hourly_rate >= 300:
            return "Grade B"
        elif hourly_rate >= 200:
            return "Grade C"
        else:
            return "Grade D"
    
    def save_bill(self, bill: Bill, output_dir: str = "generated_bills") -> str:
        """Save the bill as an HTML file."""
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate HTML content
            html_content = self.generate_bill_html(bill)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bill_of_costs_{bill.case_name}_{timestamp}.html"
            filepath = os.path.join(output_dir, filename)
            
            # Save file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Bill saved to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving bill: {str(e)}", exc_info=True)
            raise 