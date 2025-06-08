from typing import List, Optional, Dict, Any
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, HttpUrl
import uuid

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

class FeeEarnerGrade(str, Enum):
    GRADE_A = "Grade A" # Solicitors and FILEX with over 8 years' PQE
    GRADE_B = "Grade B" # Solicitors and FILEX with over 4 years' PQE
    GRADE_C = "Grade C" # Other solicitors, FILEX, and fee earners of equivalent experience
    GRADE_D = "Grade D" # Trainee solicitors, paralegals, and other fee earners
    COUNSEL_KC = "Counsel KC"
    COUNSEL_JUNIOR_OVER_10 = "Counsel Junior (Over 10 Years Call)"
    COUNSEL_JUNIOR_UNDER_10 = "Counsel Junior (Under 10 Years Call)"
    EXPERT = "Expert" # Generic, can be refined

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
    PROCESS_SERVER_FEE = "Process Server Fee"
    OTHER = "Other"

class RetainerType(str, Enum):
    PRIVATE = "Private Retainer"
    CFA = "Conditional Fee Agreement"
    DBA = "Damages Based Agreement"
    LEGAL_AID = "Legal Aid Certificate"
    PRO_BONO = "Pro Bono"

# --- Core Data Models ---

class EntityReference(BaseModel):
    """A generic reference to another entity, useful for linking."""
    entity_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    entity_type: str # e.g., "FeeEarner", "Document"
    display_name: Optional[str] = None # e.g., Fee earner's name, document title

class DocumentChunk(BaseModel):
    """Represents a chunk of text from a source document, for RAG."""
    chunk_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_document_id: uuid.UUID
    text_content: str
    page_number_start: Optional[int] = None
    page_number_end: Optional[int] = None
    embedding: Optional[List[float]] = None # To be populated by embedding model
    metadata: Dict[str, Any] = Field(default_factory=dict) # Any other relevant info

class SourceDocument(BaseModel):
    """Represents an input document consumed by the cost draftsman."""
    document_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_id: uuid.UUID
    file_name: Optional[str] = None
    file_path: Optional[str] = None # Path to original file if stored locally/cloud
    document_type: DocumentType
    date_created: Optional[date] = None # Date on document
    date_received: Optional[date] = None # Date received by firm
    author: Optional[str] = None
    recipient: Optional[str] = None
    extracted_text_path: Optional[str] = None # Path to plain text version
    # chunks: List[DocumentChunk] = Field(default_factory=list) # Chunks for RAG (can be stored separately too)
    metadata: Dict[str, Any] = Field(default_factory=dict) # e.g., OCR quality, original format

class Party(BaseModel):
    party_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_id: uuid.UUID
    name: str
    role: PartyRole
    is_represented: bool = True
    solicitor_firm_name: Optional[str] = None
    solicitor_contact_person: Optional[str] = None
    address: Optional[str] = None
    is_client_party: bool = False # Is this the party our firm represents?

class FeeEarner(BaseModel):
    fe_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    firm_id: uuid.UUID # ID of the law firm they belong to
    name: str
    role_at_firm: str # e.g., Partner, Solicitor, Paralegal, Costs Draftsman
    qualification_level: FeeEarnerGrade # Maps to Grade A-D
    experience_years: Optional[int] = None # Could be used to derive grade
    default_hourly_rate_gbp: Optional[float] = None # Base rate

class AgreedRate(BaseModel):
    """Represents an agreed hourly rate for a specific fee earner grade or individual."""
    rate_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    # Link to retainer, case, or general firm rates
    applicable_to_entity_id: uuid.UUID # e.g., case_id, retainer_id
    fee_earner_grade: Optional[FeeEarnerGrade] = None
    specific_fee_earner_id: Optional[uuid.UUID] = None
    hourly_rate_gbp: float
    currency: str = "GBP"
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    notes: Optional[str] = None

class WorkItem(BaseModel):
    """Represents a single item of work done."""
    work_item_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_id: uuid.UUID
    fee_earner_id: uuid.UUID
    date_of_work: date
    activity_type: WorkActivityType
    description: str # Detailed narrative of work done
    time_spent_units: int # e.g., 1 unit = 6 minutes
    time_spent_decimal_hours: Optional[float] = None # Calculated: time_spent_units / 10
    applicable_hourly_rate_gbp: float
    claimed_amount_gbp: Optional[float] = None # Calculated: time_spent_decimal_hours * applicable_hourly_rate_gbp
    is_recoverable: bool = True
    related_document_ids: List[uuid.UUID] = Field(default_factory=list) # Link to source docs
    source_reference: Optional[str] = None # e.g., "Attendance note 23", "Email to J.Smith"
    bill_item_number: Optional[str] = None # When part of a formal Bill of Costs
    disputed: bool = False
    dispute_reason: Optional[str] = None

class Disbursement(BaseModel):
    """Represents an expense incurred."""
    disbursement_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_id: uuid.UUID
    date_incurred: date
    disbursement_type: DisbursementType
    description: str
    payee_name: Optional[str] = None # e.g., "HMCTS", "Dr. Expert Name", "Counsel Name"
    amount_net_gbp: float
    vat_gbp: float = 0.0
    amount_gross_gbp: Optional[float] = None # Calculated: amount_net_gbp + vat_gbp
    is_recoverable: bool = True
    voucher_document_id: Optional[uuid.UUID] = None # Link to invoice/receipt
    bill_item_number: Optional[str] = None
    disputed: bool = False
    dispute_reason: Optional[str] = None

class Counsel(BaseModel):
    counsel_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    chambers_name: Optional[str] = None
    call_date: Optional[date] = None
    is_kc: bool = False
    contact_email: Optional[EmailStr] = None

class Expert(BaseModel):
    expert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    field_of_expertise: str
    organisation_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None

class CourtDetails(BaseModel):
    court_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str # e.g., "High Court of Justice, King's Bench Division"
    address: Optional[str] = None
    is_county_court: bool = False
    is_high_court: bool = False
    is_court_of_appeal: bool = False
    is_supreme_court: bool = False
    is_tribunal: bool = False
    tribunal_name: Optional[str] = None

class Retainer(BaseModel):
    """Details of the funding arrangement."""
    retainer_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_id: uuid.UUID
    retainer_type: RetainerType
    date_signed: Optional[date] = None
    document_id: Optional[uuid.UUID] = None # Link to the CFA/Client Care Letter document
    success_fee_percentage: Optional[float] = None # For CFAs
    hourly_rate_schedule_description: Optional[str] = None # Or link to AgreedRate entities
    notes: Optional[str] = None

class LawFirm(BaseModel):
    firm_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    sra_number: Optional[str] = None
    address: Optional[str] = None
    vat_number: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    website: Optional[HttpUrl] = None

class LegalCase(BaseModel):
    """The central entity representing a legal case/matter."""
    case_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    case_reference_number: str # Solicitor's internal reference
    case_name: str # e.g., "Smith v Jones"
    court_claim_number: Optional[str] = None
    our_firm_id: uuid.UUID # The firm using this system / instructing draftsman
    our_client_party_id: uuid.UUID # The party our firm represents
    
    court_details_id: Optional[uuid.UUID] = None
    date_opened: Optional[date] = None
    date_closed: Optional[date] = None
    status: Optional[str] = "Open" # e.g., Open, Closed, Costs Negotiation, Detailed Assessment
    
    # Relationships (can be stored as lists of IDs or resolved at query time)
    parties: List[Party] = Field(default_factory=list)
    fee_earners_involved_ids: List[uuid.UUID] = Field(default_factory=list)
    counsels_instructed_ids: List[uuid.UUID] = Field(default_factory=list)
    experts_instructed_ids: List[uuid.UUID] = Field(default_factory=list)
    
    retainer_details_id: Optional[uuid.UUID] = None
    
    key_dates: Dict[str, date] = Field(default_factory=dict) # e.g., "LimitationDate", "TrialDate"
    narrative_summary: Optional[str] = None # Brief overview of the case
    
    # These would be populated by extracting from input documents
    source_documents: List[SourceDocument] = Field(default_factory=list) # All input docs
    work_items: List[WorkItem] = Field(default_factory=list)
    disbursements: List[Disbursement] = Field(default_factory=list)
    
    # Generated output documents (references to their stored versions)
    # output_document_references: List[EntityReference] = Field(default_factory=list)
    # Or more specifically:
    bill_of_costs_ids: List[uuid.UUID] = Field(default_factory=list)
    schedule_of_costs_ids: List[uuid.UUID] = Field(default_factory=list)
    precedent_h_ids: List[uuid.UUID] = Field(default_factory=list)
    # ... and so on for other output document types

# --- Models for specific Output Documents (can be more detailed later) ---
# For now, we can represent generated documents by referencing their
# SourceDocument entry (with appropriate DocumentType) and storing their content.
# More structured models for outputs can be developed if needed for *editing* them.

class BillOfCostsStructure(BaseModel): # Simplified
    """Represents key structural elements if you need to model the output document itself."""
    document_id: uuid.UUID # Links to a SourceDocument of type BILL_OF_COSTS_FINAL
    case_id: uuid.UUID
    chronology_summary: Optional[str] = None
    narrative_of_dispute: Optional[str] = None
    # Sections with itemized WorkItems and Disbursements
    # This is more about the *content* of the generated document
    # which is derived from WorkItem and Disbursement lists.

class CostsBudgetPhase(BaseModel):
    phase_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    phase_name: str # e.g., "Pre-Action Costs", "Issue/Pleadings", "CMC"
    budgeted_solicitor_time_hours: Optional[float] = None
    budgeted_solicitor_cost_gbp: Optional[float] = None
    budgeted_counsel_fees_gbp: Optional[float] = None
    budgeted_expert_fees_gbp: Optional[float] = None
    budgeted_other_disbursements_gbp: Optional[float] = None
    assumptions: Optional[str] = None
    actual_solicitor_cost_gbp: Optional[float] = None # For comparison
    actual_counsel_fees_gbp: Optional[float] = None
    # ... other actuals

class CostsBudgetPrecedentH(BaseModel):
    budget_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    document_id: uuid.UUID # Links to a SourceDocument of type PRECEDENT_H
    case_id: uuid.UUID
    version_number: int = 1
    date_prepared: date
    is_agreed_by_all_parties: bool = False
    court_approved_date: Optional[date] = None
    phases: List[CostsBudgetPhase] = Field(default_factory=list)
    total_budgeted_solicitor_cost_gbp: Optional[float] = None
    total_budgeted_counsel_fees_gbp: Optional[float] = None
    # ... other totals


# --- Example Usage (Conceptual) ---
if __name__ == "__main__":
    # 1. Create a firm
    our_firm = LawFirm(name="RAG Legal LLP", sra_number="123456")

    # 2. Create a case
    case1 = LegalCase(
        case_reference_number="RL/2024/001",
        case_name="Tech Innovations Ltd vs. Old School Inc.",
        our_firm_id=our_firm.firm_id
    )

    # 3. Add parties
    client_party = Party(
        case_id=case1.case_id,
        name="Tech Innovations Ltd",
        role=PartyRole.CLAIMANT,
        is_client_party=True,
        solicitor_firm_name=our_firm.name
    )
    opponent_party = Party(
        case_id=case1.case_id,
        name="Old School Inc.",
        role=PartyRole.DEFENDANT,
        solicitor_firm_name="MegaCorp Law"
    )
    case1.parties.extend([client_party, opponent_party])
    case1.our_client_party_id = client_party.party_id

    # 4. Add a fee earner from our firm
    jane_doe = FeeEarner(
        firm_id=our_firm.firm_id,
        name="Jane Doe",
        role_at_firm="Senior Solicitor",
        qualification_level=FeeEarnerGrade.GRADE_A,
        default_hourly_rate_gbp=350.00
    )
    case1.fee_earners_involved_ids.append(jane_doe.fe_id)
    
    # 5. Add an agreed rate for this case for Grade A
    agreed_rate_case1_grade_a = AgreedRate(
        applicable_to_entity_id=case1.case_id, # Rate specific to this case
        fee_earner_grade=FeeEarnerGrade.GRADE_A,
        hourly_rate_gbp=320.00, # Negotiated rate for this case
        notes="Rate agreed with client for this matter."
    )

    # 6. Add a source document (e.g., an attendance note)
    att_note_1_text = """
    Date: 2024-07-15
    Fee Earner: Jane Doe
    Client: Tech Innovations Ltd (Mr. Smith)
    Time Spent: 1.5 hours
    Details: Call with client to discuss initial strategy. Reviewed key documents provided by client. Advised on merits.
    """
    # This text would be processed by your RAG to extract entities
    # For now, we'll manually create a SourceDocument and a WorkItem based on it.
    
    att_note_doc = SourceDocument(
        case_id=case1.case_id,
        file_name="Attendance Note 2024-07-15.docx",
        document_type=DocumentType.ATTENDANCE_NOTE,
        date_created=date(2024, 7, 15),
        author=jane_doe.name,
        # In a real RAG, you'd store the text or path to it
    )
    case1.source_documents.append(att_note_doc)

    # 7. Create a work item from that attendance note
    work_item_1 = WorkItem(
        case_id=case1.case_id,
        fee_earner_id=jane_doe.fe_id,
        date_of_work=date(2024, 7, 15),
        activity_type=WorkActivityType.ATTENDANCE_CLIENT,
        description="Call with client (Mr. Smith) to discuss initial strategy, reviewed key documents, advised on merits.",
        time_spent_units=15, # 1.5 hours * 10 units/hour
        time_spent_decimal_hours=1.5,
        applicable_hourly_rate_gbp=agreed_rate_case1_grade_a.hourly_rate_gbp, # Use the case-specific agreed rate
        claimed_amount_gbp=1.5 * agreed_rate_case1_grade_a.hourly_rate_gbp,
        related_document_ids=[att_note_doc.document_id]
    )
    case1.work_items.append(work_item_1)

    # 8. Add a disbursement (e.g., court fee)
    court_fee_voucher = SourceDocument(
        case_id=case1.case_id,
        file_name="HMCTS_Receipt_CF001.pdf",
        document_type=DocumentType.DISBURSEMENT_VOUCHER,
        date_created=date(2024,7,20)
    )
    case1.source_documents.append(court_fee_voucher)

    court_fee = Disbursement(
        case_id=case1.case_id,
        date_incurred=date(2024, 7, 20),
        disbursement_type=DisbursementType.COURT_FEE,
        description="Claim issue fee - High Court",
        payee_name="HMCTS",
        amount_net_gbp=1500.00,
        amount_gross_gbp=1500.00, # Court fees usually no VAT
        voucher_document_id=court_fee_voucher.document_id
    )
    case1.disbursements.append(court_fee)

    # --- Storing this data ---
    # You would typically serialize these Pydantic models to JSON
    # and store them in a document database (like MongoDB, Elasticsearch)
    # or a relational database (like PostgreSQL with JSONB columns, or fully normalized).
    # For RAG, Elasticsearch or a vector database is common for `DocumentChunk` with embeddings.

    # print(case1.model_dump_json(indent=2))

    # --- Generating an Output Document (Conceptual) ---
    # To generate a Bill of Costs for case1:
    # 1. Retrieve case1, its work_items, disbursements, parties, etc.
    # 2. Format them according to the Bill of Costs template (e.g., Precedent S).
    # 3. The RAG part might involve finding relevant narrative snippets from source_documents
    #    to help populate sections of the Bill.

    # To generate an N260 for a specific hearing:
    # 1. Filter work_items and disbursements for the relevant period/hearing.
    # 2. Summarize them into the N260 format.

    print(f"Case: {case1.case_name} with {len(case1.work_items)} work item(s) and {len(case1.disbursements)} disbursement(s).")
    print(f"First work item: {case1.work_items[0].description} costing £{case1.work_items[0].claimed_amount_gbp:.2f}")