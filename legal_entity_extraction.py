import re
from typing import List, Dict

# Define patterns for each entity type
ENTITY_PATTERNS = {
    "claimant": [
        r"Claimant(?:s)?:\s*([\w\s,\-&]+)",
        r"PARTIES: Claimant:\s*([\w\s,\-&]+)",
    ],
    "defendant": [
        r"Defendant(?:s)?:\s*([\w\s,\-&]+)",
        r"PARTIES: Defendant:\s*([\w\s,\-&]+)",
    ],
    "applicant": [
        r"Applicant(?:s)?:\s*([\w\s,\-&]+)",
    ],
    "respondent": [
        r"Respondent(?:s)?:\s*([\w\s,\-&]+)",
    ],
    # Add more as needed
}

def extract_entities(text: str, entity_types: List[str] = None) -> Dict[str, List[str]]:
    """
    Extract legal entities from text.
    Args:
        text: The document text.
        entity_types: List of entity types to extract (default: all in ENTITY_PATTERNS).
    Returns:
        Dict mapping entity type to list of extracted names.
    """
    results = {}
    types_to_check = entity_types or ENTITY_PATTERNS.keys()
    for entity in types_to_check:
        names = []
        for pattern in ENTITY_PATTERNS.get(entity, []):
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                names.extend([name.strip() for name in m.split(',') if name.strip()])
        # Numbered lists (optional, for all entities)
        if re.search(entity, text, re.IGNORECASE):
            numbered = re.findall(r'\d+\.\s*([\w\s,\-&]+)', text)
            names.extend([n.strip() for n in numbered])
        results[entity] = list(set(names))
    return results 