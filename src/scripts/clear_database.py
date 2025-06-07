from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

def clear_database():
    """Clear all data from the Neo4j database."""
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    )

    try:
        with driver.session() as session:
            # Delete all relationships and nodes
            result = session.run("""
                MATCH (n)
                DETACH DELETE n
            """)
            
            # Get the count of deleted nodes
            count_result = session.run("""
                MATCH (n)
                RETURN count(n) as count
            """)
            count = count_result.single()["count"]
            
            print(f"\nDatabase cleared successfully!")
            print(f"Remaining nodes: {count}")
            
    finally:
        driver.close()

if __name__ == "__main__":
    # Ask for confirmation
    response = input("Are you sure you want to clear the entire database? This cannot be undone! (yes/no): ")
    if response.lower() == 'yes':
        clear_database()
    else:
        print("Operation cancelled.") 