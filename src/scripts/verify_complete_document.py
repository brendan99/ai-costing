from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, TextLoader
import difflib
import re

load_dotenv()

def normalize_content(content: str) -> str:
    """Normalize content by removing extra whitespace and normalizing line endings."""
    # Replace multiple spaces with a single space
    content = re.sub(r'\s+', ' ', content)
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in content.split('\n')]
    # Remove empty lines
    lines = [line for line in lines if line]
    return '\n'.join(lines)

def get_original_content(file_path: str) -> str:
    """Get the original content from the file."""
    file_path = Path(file_path).resolve()  # Get absolute path
    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")
        
    file_extension = file_path.suffix.lower()
    
    if file_extension == '.pdf':
        loader = PyPDFLoader(str(file_path))
    elif file_extension == '.txt':
        loader = TextLoader(str(file_path))
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")
    
    documents = loader.load()
    content = "\n".join(doc.page_content for doc in documents)
    return normalize_content(content)

def get_ingested_content(driver: GraphDatabase.driver, case_id: str, file_name: str) -> str:
    """Get the content from Neo4j."""
    with driver.session() as session:
        # First, try to find the case by title if a UUID is not provided
        if not case_id.startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f')):
            result = session.run("""
                MATCH (c:Case {title: $case_id})
                RETURN c.id as case_id
            """, case_id=case_id)
            record = result.single()
            if record:
                case_id = record["case_id"]
            else:
                raise ValueError(f"Case with title '{case_id}' not found")

        result = session.run("""
            MATCH (c:Case {id: $case_id})-[:HAS_DOCUMENT_CHUNK]->(dc:DocumentChunk)
            WHERE dc.source_file = $file_name
            RETURN dc.content as content
            ORDER BY dc.page, dc.chunk_index
        """, case_id=case_id, file_name=file_name)
        
        content = "\n".join(record["content"] for record in result)
        return normalize_content(content)

def verify_document_content(file_path: str, case_id: str):
    """Verify that all content from the file has been ingested correctly."""
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    )

    try:
        # Get original content
        original_content = get_original_content(file_path)
        
        # Get ingested content
        file_name = Path(file_path).name
        ingested_content = get_ingested_content(driver, case_id, file_name)
        
        # Compare contents
        print(f"\nVerifying content for file: {file_name}")
        print("-" * 80)
        print(f"Original content length: {len(original_content)} characters")
        print(f"Ingested content length: {len(ingested_content)} characters")
        
        if original_content == ingested_content:
            print("\n✅ Content verification successful! All content has been ingested correctly.")
        else:
            print("\n❌ Content verification failed! Differences found:")
            # Show differences
            diff = difflib.unified_diff(
                original_content.splitlines(),
                ingested_content.splitlines(),
                lineterm='',
                n=3
            )
            print('\n'.join(diff))
            
    finally:
        driver.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Verify document content in Neo4j database')
    parser.add_argument('--file', required=True, help='Path to the document file')
    parser.add_argument('--case-id', required=True, help='Case ID or title in the database')
    
    args = parser.parse_args()
    verify_document_content(args.file, args.case_id) 