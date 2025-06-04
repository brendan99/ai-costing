import re
from typing import List

LEGAL_HEADINGS = [
    r"\\bPARTIES\\b",
    r"\\bCLAIMANT(?:S)?\\b",
    r"\\bDEFENDANT(?:S)?\\b",
    r"\\bAPPLICANT(?:S)?\\b",
    r"\\bRESPONDENT(?:S)?\\b",
    r"\\bSTATEMENTS FILED\\b",
    r"\\bWITNESS(?:ES)?\\b",
    r"\\bBACKGROUND\\b",
    r"\\bCASE SUMMARY\\b",
    r"\\bCOSTS\\b",
    r"\\bDISBURSEMENTS\\b",
    r"\\bPROCEEDINGS\\b",
    r"\\bORDER\\b",
    r"\\bJUDGMENT\\b",
    # Add more as needed
]

def split_by_legal_headings(text: str) -> List[str]:
    """Split text into chunks at legal section headings, keeping headings with their content."""
    pattern = r"(?i)(?=^(" + "|".join(LEGAL_HEADINGS) + r")[^\n]*$)"
    splits = [m.start() for m in re.finditer(pattern, text, flags=re.MULTILINE)]
    if not splits or splits[0] != 0:
        splits = [0] + splits
    chunks = []
    for i in range(len(splits)):
        start = splits[i]
        end = splits[i+1] if i+1 < len(splits) else len(text)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
    return chunks

def legal_aware_chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Chunk text by legal headings, then fallback to sliding window chunking for long sections."""
    section_chunks = split_by_legal_headings(text)
    final_chunks = []
    for section in section_chunks:
        if len(section) > chunk_size * 2:
            # Fallback to sliding window chunking
            final_chunks.extend(sliding_window_chunk(section, chunk_size, overlap))
        else:
            final_chunks.append(section)
    return final_chunks

def sliding_window_chunk(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split text into overlapping chunks (sliding window)."""
    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = start + chunk_size
        if end > text_length:
            end = text_length
        chunk = text[start:end]
        chunks.append(chunk)
        if end == text_length or chunk_size <= overlap:
            break
        start = end - overlap
    return chunks 