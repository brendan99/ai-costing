from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

def check_database_content():
    """Check what content exists in the database."""
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    )

    try:
        with driver.session() as session:
            # Check all nodes
            result = session.run("""
                MATCH (n)
                RETURN labels(n) as labels, count(*) as count
            """)
            print("\nNode counts by type:")
            print("-" * 40)
            for record in result:
                print(f"{record['labels']}: {record['count']}")

            # Check document chunks
            result = session.run("""
                MATCH (c:Case)-[:HAS_DOCUMENT_CHUNK]->(dc:DocumentChunk)
                RETURN c.id as case_id, 
                       c.title as case_title,
                       count(dc) as chunk_count,
                       collect(distinct dc.source_file) as files
            """)
            print("\nDocument chunks by case:")
            print("-" * 40)
            for record in result:
                print(f"Case {record['case_id']} ({record['case_title']}):")
                print(f"  Chunks: {record['chunk_count']}")
                print(f"  Files: {record['files']}")

            # Check a sample of document chunks
            result = session.run("""
                MATCH (c:Case)-[:HAS_DOCUMENT_CHUNK]->(dc:DocumentChunk)
                RETURN c.id as case_id,
                       dc.source_file as file,
                       dc.page as page,
                       dc.chunk_index as chunk_index,
                       dc.content as content
                LIMIT 5
            """)
            print("\nSample document chunks:")
            print("-" * 40)
            for record in result:
                print(f"Case {record['case_id']}, File: {record['file']}")
                print(f"Page {record['page']}, Chunk {record['chunk_index']}")
                print(f"Content: {record['content'][:100]}...")
                print()

    finally:
        driver.close()

if __name__ == "__main__":
    check_database_content() 