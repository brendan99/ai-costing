import os
import sys
from pathlib import Path
import pytest
from neo4j import GraphDatabase

# Add the src directory to the Python path
src_path = str(Path(__file__).parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

# Set up test environment variables
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "password"
os.environ["NEO4J_DATABASE"] = "neo4j"  # Use the default database

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment before running tests."""
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
    )
    
    # Clean up any existing test data
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    
    driver.close()
    yield
    
    # Clean up after all tests
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
    )
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    driver.close()

@pytest.fixture(autouse=True)
def cleanup_database():
    """Clean up the database before each test."""
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
    )
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    driver.close()
    yield 