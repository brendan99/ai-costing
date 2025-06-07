from langchain_ollama import OllamaLLM
from langchain_ollama import OllamaEmbeddings
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Neo4jVector
from langchain.embeddings.base import Embeddings
from langchain.llms.base import LLM
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
from langchain_community.llms import Ollama
from langchain_community.embeddings import OllamaEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_core.output_parsers import StrOutputParser

from ..models.domain import Case, DocumentType

load_dotenv()

class LLMOperations:
    def __init__(self):
        """Initialize LLM operations with Ollama."""
        self.llm = OllamaLLM(
            model="mistral",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
        
        self.embeddings = OllamaEmbeddings(
            model="nomic-embed-text",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False
        )
    
    def split_text(self, text: str) -> List[str]:
        """Split text into chunks."""
        return self.text_splitter.split_text(text)
    
    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for a list of texts."""
        return self.embeddings.embed_documents(texts)
    
    def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from text using LLM."""
        prompt = PromptTemplate(
            input_variables=["text"],
            template="""
            Extract the following information from the text:
            - Case Reference (if found)
            - Case Title
            - Court Name
            - Brief Description
            
            If any information is not found, use reasonable defaults.
            
            Text:
            {text}
            
            Return the information in this format:
            Case Reference: [reference]
            Title: [title]
            Court: [court]
            Description: [description]
            """
        )
        
        chain = prompt | self.llm
        
        result = chain.invoke({"text": text})
        
        # Parse the result
        lines = result.strip().split('\n')
        entities = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                entities[key.strip()] = value.strip()
        
        return entities

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text string."""
        return self.embeddings.embed_query(text)

    def generate_document(self, case: Case, doc_type: DocumentType) -> str:
        """Generate a legal document using LLM."""
        # Construct prompt based on document type
        if doc_type == DocumentType.BILL_OF_COSTS:
            prompt = self._get_bill_of_costs_prompt()
        elif doc_type == DocumentType.SCHEDULE_OF_COSTS:
            prompt = self._get_schedule_of_costs_prompt()
        elif doc_type == DocumentType.POINTS_OF_DISPUTE:
            prompt = self._get_points_of_dispute_prompt()
        else:
            prompt = self._get_points_of_reply_prompt()

        chain = LLMChain(
            llm=self.llm,
            prompt=prompt,
            output_parser=StrOutputParser()
        )

        # Prepare case data for the prompt
        case_data = {
            "case_reference": case.reference,
            "case_title": case.title,
            "court": case.court or "Not specified",
            "work_items": [
                {
                    "date": item.date.strftime("%Y-%m-%d"),
                    "description": item.description,
                    "time_spent": f"{item.time_spent_units} units",
                    "amount": f"£{item.amount:.2f}"
                }
                for item in case.work_items
            ],
            "disbursements": [
                {
                    "date": d.date.strftime("%Y-%m-%d"),
                    "description": d.description,
                    "amount": f"£{d.amount:.2f}"
                }
                for d in case.disbursements
            ]
        }

        return chain.invoke(case_data)

    def _get_bill_of_costs_prompt(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=[
                "case_reference",
                "case_title",
                "court",
                "work_items",
                "disbursements"
            ],
            template="""
            Generate a Bill of Costs for the following case:

            Case Reference: {case_reference}
            Case Title: {case_title}
            Court: {court}

            Work Items:
            {work_items}

            Disbursements:
            {disbursements}

            Please format the Bill of Costs according to standard UK legal practice, including:
            1. Case details and court information
            2. Chronological list of work items with dates, descriptions, time spent, and amounts
            3. List of disbursements
            4. Summary of costs
            5. VAT calculations if applicable

            Format the output in a clear, professional manner suitable for court submission.
            """
        )

    def _get_schedule_of_costs_prompt(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=[
                "case_reference",
                "case_title",
                "court",
                "work_items",
                "disbursements"
            ],
            template="""
            Generate a Schedule of Costs for the following case:

            Case Reference: {case_reference}
            Case Title: {case_title}
            Court: {court}

            Work Items:
            {work_items}

            Disbursements:
            {disbursements}

            Please format the Schedule of Costs according to standard UK legal practice, including:
            1. Case details
            2. Summary of costs by category
            3. Breakdown of work items
            4. Breakdown of disbursements
            5. Total costs

            Format the output in a clear, professional manner suitable for court submission.
            """
        )

    def _get_points_of_dispute_prompt(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=[
                "case_reference",
                "case_title",
                "court",
                "work_items",
                "disbursements"
            ],
            template="""
            Generate Points of Dispute for the following case:

            Case Reference: {case_reference}
            Case Title: {case_title}
            Court: {court}

            Work Items:
            {work_items}

            Disbursements:
            {disbursements}

            Please format the Points of Dispute according to standard UK legal practice, including:
            1. Introduction and case details
            2. Specific points of dispute for each work item or category
            3. Justification for each point of dispute
            4. Alternative figures proposed where applicable
            5. Conclusion

            Format the output in a clear, professional manner suitable for court submission.
            """
        )

    def _get_points_of_reply_prompt(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=[
                "case_reference",
                "case_title",
                "court",
                "work_items",
                "disbursements"
            ],
            template="""
            Generate Points of Reply for the following case:

            Case Reference: {case_reference}
            Case Title: {case_title}
            Court: {court}

            Work Items:
            {work_items}

            Disbursements:
            {disbursements}

            Please format the Points of Reply according to standard UK legal practice, including:
            1. Introduction and case details
            2. Response to each point of dispute
            3. Justification for the original figures
            4. Supporting arguments and evidence
            5. Conclusion

            Format the output in a clear, professional manner suitable for court submission.
            """
        ) 