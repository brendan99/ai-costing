import re
import requests
from typing import List
from legal_entities_models import Party, LegalEntities
import streamlit as st

# LLM-based extraction using Ollama
OLLAMA_URL = "http://localhost:11434/api/chat"  # Use chat endpoint
OLLAMA_MODEL = "llama3.1:8b"  # Updated to match installed model

def extract_entities_llm(text: str, entity_type: str = "claimant") -> list:
    prompt = f"""
    Extract all {entity_type}s from the following legal text. Return a JSON list of objects, each with 'name' and 'role' fields. Do not include explanations.

    Text:
    {text}
    """
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        import json
        content = response.json().get('message', {}).get('content', '').strip()
        print(f"[LLM RAW RESPONSE] For entity_type={entity_type}: {content[:500]}")
        
        # Store the raw response in session state
        if 'llm_responses' in st.session_state:
            st.session_state.llm_responses.append({
                'entity_type': entity_type,
                'content': content
            })
        
        # Remove markdown code block markers and explanations
        content_clean = content
        content_clean = re.sub(r"```(?:json)?", "", content_clean, flags=re.IGNORECASE)
        content_clean = re.sub(r"```", "", content_clean)
        # Extract the first JSON array in the text
        match = re.search(r'\[.*?\]', content_clean, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        # Fallback: try to parse the cleaned content directly
        try:
            return json.loads(content_clean)
        except Exception:
            return []
    except Exception as e:
        print(f"[LLM Extraction Error] {e} | Raw content: {content if 'content' in locals() else 'N/A'}")
        return []

def extract_entities(text: str, entity_types: List[str] = None) -> LegalEntities:
    """
    Extract legal entities from text using LLM extraction (Ollama) for all entity types.
    Adds a 'source' attribute to Party: 'llm'.
    """
    results = {}
    types_to_check = entity_types or ["claimant", "defendant", "applicant", "respondent"]
    for entity in types_to_check:
        parties = []
        llm_entities = extract_entities_llm(text, entity_type=entity)
        if isinstance(llm_entities, list):
            for item in llm_entities:
                if isinstance(item, dict) and "name" in item:
                    role_val = item.get("role", entity)
                    if not role_val:
                        role_val = entity
                    role_val = str(role_val)
                    parties.append(Party(
                        name=item["name"].strip(),
                        role=role_val,
                        address=None,
                        source="llm"
                    ))
                elif isinstance(item, str):
                    parties.append(Party(
                        name=item.strip(),
                        role=entity,
                        address=None,
                        source="llm"
                    ))
        results[entity] = parties
    legal_entities_kwargs = {k: v for k, v in results.items() if hasattr(LegalEntities, k)}
    return LegalEntities(**legal_entities_kwargs) 