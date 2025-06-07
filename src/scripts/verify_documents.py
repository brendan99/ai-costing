from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

def verify_documents():
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    )

    try:
        with driver.session() as session:
            # Get all cases and their document chunks
            result = session.run("""
                MATCH (c:Case)-[:HAS_DOCUMENT_CHUNK]->(dc:DocumentChunk)
                RETURN 
                    c.title as case_title,
                    c.reference as case_reference,
                    count(dc) as chunk_count,
                    collect(DISTINCT dc.source_file) as files
                ORDER BY c.title
            """)
            
            print("\nCases and their document chunks:")
            print("-" * 80)
            for record in result:
                print(f"Case Title: {record['case_title']}")
                print(f"Case Reference: {record['case_reference']}")
                print(f"Number of chunks: {record['chunk_count']}")
                print(f"Files: {', '.join(record['files'])}")
                print("-" * 80)

            # Get a sample of document chunks
            print("\nSample of document chunks:")
            print("-" * 80)
            result = session.run("""
                MATCH (c:Case)-[:HAS_DOCUMENT_CHUNK]->(dc:DocumentChunk)
                RETURN 
                    c.title as case_title,
                    dc.source_file as file,
                    dc.page as page,
                    substring(dc.content, 0, 100) as content_preview
                LIMIT 5
            """)
            
            for record in result:
                print(f"Case: {record['case_title']}")
                print(f"File: {record['file']}")
                print(f"Page: {record['page']}")
                print(f"Content preview: {record['content_preview']}...")
                print("-" * 80)

    finally:
        driver.close()

if __name__ == "__main__":
    verify_documents() 