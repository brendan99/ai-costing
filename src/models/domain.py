from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    BILL_OF_COSTS = "Bill of Costs"
    SCHEDULE_OF_COSTS = "Schedule of Costs"
    POINTS_OF_DISPUTE = "Points of Dispute"
    POINTS_OF_REPLY = "Points of Reply"


class FeeEarner(BaseModel):
    id: str = Field(..., description="Unique identifier for the fee earner")
    name: str = Field(..., description="Full name of the fee earner")
    grade: str = Field(..., description="Grade/level of the fee earner")
    hourly_rate: Decimal = Field(..., description="Hourly rate in GBP")


class WorkItem(BaseModel):
    id: str = Field(..., description="Unique identifier for the work item")
    date: datetime = Field(..., description="Date when the work was performed")
    description: str = Field(..., description="Description of the work performed")
    time_spent_units: int = Field(..., description="Time spent in units (typically 6 minutes)")
    fee_earner_id: str = Field(..., description="ID of the fee earner who performed the work")
    amount: Decimal = Field(..., description="Amount claimed in GBP")
    category: Optional[str] = Field(None, description="Category of work (e.g., 'Pre-action', 'Disclosure')")


class Disbursement(BaseModel):
    id: str = Field(..., description="Unique identifier for the disbursement")
    date: datetime = Field(..., description="Date of the disbursement")
    description: str = Field(..., description="Description of the disbursement")
    amount: Decimal = Field(..., description="Amount in GBP")
    vat_amount: Optional[Decimal] = Field(None, description="VAT amount if applicable")
    category: Optional[str] = Field(None, description="Category of disbursement")


class Case(BaseModel):
    id: str = Field(..., description="Unique identifier for the case")
    reference: str = Field(..., description="Case reference number")
    title: str = Field(..., description="Case title")
    court: Optional[str] = Field(None, description="Court name")
    description: Optional[str] = Field(None, description="Case description")
    work_items: List[WorkItem] = Field(default_factory=list)
    disbursements: List[Disbursement] = Field(default_factory=list)
    fee_earners: List[FeeEarner] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentChunk(BaseModel):
    id: str = Field(..., description="Unique identifier for the chunk")
    case_id: Optional[str] = None  # Make case_id optional since it will be set when creating the chunk
    content: str = Field(..., description="Text content of the chunk")
    metadata: dict = Field(default_factory=dict, description="Additional metadata about the chunk")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding of the chunk")
    source_file: str = Field(..., description="Source file of the chunk")
    page_number: int = Field(..., description="Page number of the chunk")
    chunk_index: int = Field(..., description="Index of the chunk")
    created_at: datetime = Field(default_factory=datetime.utcnow) 