from typing import List, Optional, Dict, Any
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl, EmailStr, validator
import uuid
import re

# Email validation pattern
EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

def validate_email(email: str) -> bool:
    return bool(re.match(EMAIL_PATTERN, email))

# --- Enums for controlled vocabularies ---

class PartyRole(str, Enum):
    CLAIMANT = "Claimant"
    DEFENDANT = "Defendant"
    APPLICANT = "Applicant"
    RESPONDENT = "Respondent"
    PAYING_PARTY = "Paying Party"
    RECEIVING_PARTY = "Receiving Party"
    OTHER = "Other"

class DocumentType(str, Enum):
    ATTENDANCE_NOTE = "Attendance Note"
    LETTER_IN = "Letter In"
    LETTER_OUT = "Letter Out"
    EMAIL_IN = "Email In"
    EMAIL_OUT = "Email Out"
    CLAIM_FORM = "Claim Form"
    DEFENCE = "Defence"
    COURT_ORDER = "Court Order"
    WITNESS_STATEMENT = "Witness Statement"
    EXPERT_REPORT = "Expert Report"
    COUNSEL_FEE_NOTE = "Counsel Fee Note"
    DISBURSEMENT_VOUCHER = "Disbursement Voucher"
    TIME_LEDGER = "Time Ledger"
    CLIENT_CARE_LETTER = "Client Care Letter"
    CFA = "Conditional Fee Agreement"
    DBA = "Damages Based Agreement"
    BILL_OF_COSTS_DRAFT = "Bill of Costs (Draft)"
    BILL_OF_COSTS_FINAL = "Bill of Costs (Final)"
    SCHEDULE_OF_COSTS = "Schedule of Costs"
    PRECEDENT_H = "Costs Budget (Precedent H)"
    PRECEDENT_R = "Budget Discussion Report (Precedent R)"
    N260_STATEMENT_OF_COSTS = "Statement of Costs (N260)"
    POINTS_OF_DISPUTE = "Points of Dispute"
    REPLIES_TO_POD = "Replies to Points of Dispute"
    N252_NOTICE_OF_COMMENCEMENT = "Notice of Commencement (N252)"
    DEFAULT_COSTS_CERTIFICATE_APP = "Application for Default Costs Certificate"
    INSTRUCTIONS_TO_COUNSEL = "Instructions to Counsel"
    ADVICE_ON_COSTS = "Advice on Costs"
    LEGAL_AID_CLAIM_FORM = "Legal Aid Claim Form"
    HIGH_COSTS_CASE_PLAN = "High Costs Case Plan"
    OTHER_INPUT = "Other Input Document"
    OTHER_OUTPUT = "Other Output Document"
    CORRESPONDENCE = "Correspondence"
    INVOICE = "Invoice"

class FeeEarnerGrade(str, Enum):
    GRADE_A = "Grade A"
    GRADE_B = "Grade B"
    GRADE_C = "Grade C"
    GRADE_D = "Grade D"
    COUNSEL_KC = "Counsel KC"
    COUNSEL_JUNIOR_OVER_10 = "Counsel Junior (Over 10 Years Call)"
    COUNSEL_JUNIOR_UNDER_10 = "Counsel Junior (Under 10 Years Call)"
    EXPERT = "Expert"

class WorkActivityType(str, Enum):
    ATTENDANCE_CLIENT = "Attendance on Client"
    ATTENDANCE_WITNESS = "Attendance on Witness"
    ATTENDANCE_COUNSEL = "Attendance on Counsel"
    ATTENDANCE_COURT = "Attendance at Court"
    ATTENDANCE_OTHER_SIDE = "Attendance on Other Side"
    ATTENDANCE_INTERNAL = "Attendance Internal"
    PREPARATION = "Preparation"
    DRAFTING = "Drafting"
    RESEARCH = "Research"
    REVIEW = "Review"
    COMMUNICATIONS_IN = "Communications In (Letters/Emails)"
    COMMUNICATIONS_OUT = "Communications Out (Letters/Emails)"
    TRAVEL = "Travel"
    WAITING = "Waiting"
    REPORTING = "Reporting"

class DisbursementType(str, Enum):
    COURT_FEE = "Court Fee"
    COUNSEL_FEE = "Counsel's Fee"
    EXPERT_FEE = "Expert's Fee"
    TRAVEL_EXPENSE = "Travel Expense"
    PHOTOCOPYING = "Photocopying (External)"
    PROCESS_SERVER = "Process Server Fee"
    OTHER = "Other"

class RetainerType(str, Enum):
    PRIVATE = "Private Retainer"
    CFA = "Conditional Fee Agreement"
    DBA = "Damages Based Agreement"
    LEGAL_AID = "Legal Aid Certificate"
    PRO_BONO = "Pro Bono"

class ActivityType(str, Enum):
    ATTENDANCE_ON_CLIENT = "Attendance on Client"
    ATTENDANCE_ON_WITNESS = "Attendance on Witness"
    ATTENDANCE_ON_COUNSEL = "Attendance on Counsel"
    ATTENDANCE_AT_COURT = "Attendance at Court"
    ATTENDANCE_ON_OTHER_SIDE = "Attendance on Other Side"
    ATTENDANCE_INTERNAL = "Attendance Internal"
    PREPARATION = "Preparation"
    DRAFTING = "Drafting"
    RESEARCH = "Research"
    REVIEW = "Review"
    COMMUNICATIONS_IN = "Communications In (Letters/Emails)"
    COMMUNICATIONS_OUT = "Communications Out (Letters/Emails)"
    TRAVEL = "Travel"
    WAITING = "Waiting"
    REPORTING = "Reporting"

# --- Core Data Models ---

class EntityReference(BaseModel):
    entity_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    entity_type: str
    display_name: Optional[str] = None

class DocumentChunk(BaseModel):
    chunk_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_document_id: uuid.UUID
    text_content: str
    page_number_start: Optional[int] = None
    page_number_end: Optional[int] = None
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SourceDocument(BaseModel):
    document_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_id: uuid.UUID
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    document_type: DocumentType
    date_created: Optional[date] = None
    date_received: Optional[date] = None
    author: Optional[str] = None
    recipient: Optional[str] = None
    extracted_text_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Party(BaseModel):
    party_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_id: uuid.UUID
    name: str
    role: PartyRole
    is_represented: bool = True
    solicitor_firm_name: Optional[str] = None
    solicitor_contact_person: Optional[str] = None
    address: Optional[str] = None
    is_client_party: bool = False

class FeeEarner(BaseModel):
    fe_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    firm_id: uuid.UUID
    name: str
    role_at_firm: str
    qualification_level: FeeEarnerGrade
    experience_years: Optional[int] = None
    default_hourly_rate_gbp: Optional[float] = None

class AgreedRate(BaseModel):
    rate_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    applicable_to_entity_id: uuid.UUID
    fee_earner_grade: Optional[FeeEarnerGrade] = None
    specific_fee_earner_id: Optional[uuid.UUID] = None
    hourly_rate_gbp: float
    currency: str = "GBP"
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    notes: Optional[str] = None

class WorkItem(BaseModel):
    work_item_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_id: uuid.UUID
    fee_earner_id: Optional[uuid.UUID] = None
    date_of_work: date
    activity_type: WorkActivityType
    description: str
    time_spent_units: Optional[int] = 0
    time_spent_decimal_hours: Optional[float] = 0.0
    applicable_hourly_rate_gbp: Optional[float] = 0.0
    claimed_amount_gbp: Optional[float] = 0.0
    is_recoverable: bool = True
    related_document_ids: List[uuid.UUID] = Field(default_factory=list)
    source_reference: Optional[str] = None
    bill_item_number: Optional[str] = None
    disputed: bool = False
    dispute_reason: Optional[str] = None

class Disbursement(BaseModel):
    disbursement_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_id: uuid.UUID
    date_incurred: date
    disbursement_type: DisbursementType
    description: str
    payee_name: Optional[str] = None
    amount_net_gbp: float
    vat_gbp: float = 0.0
    amount_gross_gbp: Optional[float] = None
    is_recoverable: bool = True
    voucher_document_id: Optional[uuid.UUID] = None
    bill_item_number: Optional[str] = None
    disputed: bool = False
    dispute_reason: Optional[str] = None

class Counsel(BaseModel):
    counsel_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    chambers_name: Optional[str] = None
    call_date: Optional[date] = None
    is_kc: bool = False
    contact_email: Optional[str] = Field(None, pattern=EMAIL_PATTERN)

class Expert(BaseModel):
    expert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    field_of_expertise: str
    organisation_name: Optional[str] = None
    contact_email: Optional[str] = Field(None, pattern=EMAIL_PATTERN)

class CourtDetails(BaseModel):
    court_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    address: Optional[str] = None
    is_county_court: bool = False
    is_high_court: bool = False
    is_court_of_appeal: bool = False
    is_supreme_court: bool = False
    is_tribunal: bool = False
    tribunal_name: Optional[str] = None

class Retainer(BaseModel):
    retainer_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_id: uuid.UUID
    retainer_type: RetainerType
    date_signed: Optional[date] = None
    document_id: Optional[uuid.UUID] = None
    success_fee_percentage: Optional[float] = None
    hourly_rate_schedule_description: Optional[str] = None
    notes: Optional[str] = None

class LawFirm(BaseModel):
    firm_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    sra_number: Optional[str] = None
    address: Optional[str] = None
    vat_number: Optional[str] = None
    contact_email: Optional[str] = Field(None, pattern=EMAIL_PATTERN)
    website: Optional[HttpUrl] = None

class LegalCase(BaseModel):
    case_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_reference_number: str
    case_name: str
    court_claim_number: Optional[str] = None
    our_firm_id: uuid.UUID
    our_client_party_id: uuid.UUID
    court_details_id: Optional[uuid.UUID] = None
    date_opened: Optional[date] = None
    date_closed: Optional[date] = None
    status: Optional[str] = "Open"
    parties: List[Party] = Field(default_factory=list)
    fee_earners_involved_ids: List[uuid.UUID] = Field(default_factory=list)
    counsels_instructed_ids: List[uuid.UUID] = Field(default_factory=list)
    experts_instructed_ids: List[uuid.UUID] = Field(default_factory=list)
    retainer_details_id: Optional[uuid.UUID] = None
    key_dates: Dict[str, date] = Field(default_factory=dict)
    narrative_summary: Optional[str] = None
    source_documents: List[SourceDocument] = Field(default_factory=list)
    work_items: List[WorkItem] = Field(default_factory=list)
    disbursements: List[Disbursement] = Field(default_factory=list)
    bill_of_costs_ids: List[uuid.UUID] = Field(default_factory=list)
    schedule_of_costs_ids: List[uuid.UUID] = Field(default_factory=list)
    precedent_h_ids: List[uuid.UUID] = Field(default_factory=list)

class BillItem(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: datetime
    description: str
    amount: float
    is_recoverable: bool = True

class BillSection(BaseModel):
    section_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    items: List[BillItem]

class Bill(BaseModel):
    bill_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str
    case_name: str
    date_generated: datetime
    sections: List[BillSection]
    total_amount: float
    recoverable_amount: float

    @validator('recoverable_amount')
    def validate_recoverable_amount(cls, v, values):
        if 'total_amount' in values:
            if v > values['total_amount']:
                raise ValueError("Recoverable amount cannot exceed total amount")
        return v

    @validator('total_amount')
    def validate_total_amount(cls, v, values):
        if 'recoverable_amount' in values:
            if v < values['recoverable_amount']:
                raise ValueError("Total amount cannot be less than recoverable amount")
        return v 