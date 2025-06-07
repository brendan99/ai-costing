from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
import jinja2
from ..models.domain import Case, WorkItem, FeeEarner, DocumentType
from ..llm.operations import LLMOperations
from ..graph.operations import Neo4jGraph

class BillGenerator:
    def __init__(self):
        self.llm_ops = LLMOperations()
        self.graph = Neo4jGraph()
        self.template_loader = jinja2.FileSystemLoader(searchpath="./templates")
        self.template_env = jinja2.Environment(loader=self.template_loader)
        
    def generate_bill(self, case_id: str) -> str:
        """Generate a bill of costs using RAG."""
        # 1. Get case data from Neo4j
        case = self.graph.get_case(case_id)
        if not case:
            raise ValueError(f"Case not found: {case_id}")

        # 2. Get relevant document chunks for context
        chunks = self._get_relevant_chunks(case)
        
        # 3. Format work items by fee earner grade
        work_items_by_grade = self._group_work_items_by_grade(case.work_items)
        
        # 4. Calculate totals
        totals = self._calculate_totals(case)
        
        # 5. Generate bill using template
        template = self.template_env.get_template("bill_of_costs.html")
        bill_html = template.render(
            case=case,
            work_items_by_grade=work_items_by_grade,
            disbursements=case.disbursements,
            totals=totals,
            generated_date=datetime.now().strftime("%d.%m.%Y")
        )
        
        return bill_html
    
    def _get_relevant_chunks(self, case: Case) -> List[Dict[str, Any]]:
        """Get relevant document chunks for bill generation context."""
        query = f"Case {case.reference} work items, time spent, and amounts for Bill of Costs"
        query_embedding = self.llm_ops.get_embedding(query)
        return self.graph.search_similar_chunks(query_embedding, limit=5)
    
    def _group_work_items_by_grade(self, work_items: List[WorkItem]) -> Dict[str, List[WorkItem]]:
        """Group work items by fee earner grade."""
        grouped = {}
        for item in work_items:
            grade = item.fee_earner.grade
            if grade not in grouped:
                grouped[grade] = []
            grouped[grade].append(item)
        return grouped
    
    def _calculate_totals(self, case: Case) -> Dict[str, float]:
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
    
    def save_bill(self, content: str, case: Case) -> Path:
        """Save the generated bill to a file."""
        output_dir = Path("output/bills")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = output_dir / f"bill_of_costs_{case.reference}_{datetime.now().strftime('%Y%m%d')}.html"
        with open(file_path, "w") as f:
            f.write(content)
        
        return file_path 