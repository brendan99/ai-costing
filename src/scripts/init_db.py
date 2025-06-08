#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import logging
import typer
from rich.console import Console
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

# Add project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from src.graph.operations import Neo4jGraph

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()
console = Console()

def drop_existing_indexes(driver):
    """Drop existing indexes and constraints."""
    with driver.session() as session:
        # Drop constraints first
        session.run("""
            CALL apoc.schema.assert({},{},true)
        """)
        console.print("[yellow]Dropped existing constraints[/yellow]")
        
        # Drop indexes
        session.run("""
            CALL apoc.schema.assert({},{},true)
        """)
        console.print("[yellow]Dropped existing indexes[/yellow]")

def create_indexes(driver):
    """Create necessary indexes in Neo4j."""
    with driver.session() as session:
        # Create vector index for document chunks
        try:
            session.run("""
            CREATE VECTOR INDEX document_chunks IF NOT EXISTS
            FOR (dc:DocumentChunk)
            ON (dc.embedding)
            OPTIONS {
                indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }
            }
            """)
            console.print("[green]Created vector index for document chunks[/green]")
        except Exception as e:
            console.print(f"[yellow]Note: Vector index creation failed (might already exist): {e}[/yellow]")

        # Create indexes for case reference and IDs
        try:
            session.run("CREATE INDEX case_reference IF NOT EXISTS FOR (c:Case) ON (c.reference)")
            session.run("CREATE INDEX case_id IF NOT EXISTS FOR (c:Case) ON (c.id)")
            session.run("CREATE INDEX work_item_id IF NOT EXISTS FOR (w:WorkItem) ON (w.id)")
            session.run("CREATE INDEX fee_earner_id IF NOT EXISTS FOR (f:FeeEarner) ON (f.id)")
            session.run("CREATE INDEX document_chunk_id IF NOT EXISTS FOR (dc:DocumentChunk) ON (dc.id)")
            console.print("[green]Created property indexes[/green]")
        except Exception as e:
            console.print(f"[yellow]Note: Property index creation failed (might already exist): {e}[/yellow]")

def create_constraints(driver):
    """Create necessary constraints in Neo4j."""
    with driver.session() as session:
        try:
            # Drop existing indexes first to avoid conflicts
            session.run("DROP INDEX case_id IF EXISTS")
            session.run("DROP INDEX document_id IF EXISTS")
            session.run("DROP INDEX chunk_id IF EXISTS")
            session.run("DROP INDEX work_item_id IF EXISTS")
            session.run("DROP INDEX disbursement_id IF EXISTS")
            session.run("DROP INDEX fee_earner_id IF EXISTS")
            
            # Create constraints
            session.run("CREATE CONSTRAINT constraint_case_id IF NOT EXISTS FOR (c:Case) REQUIRE c.id IS UNIQUE")
            session.run("CREATE CONSTRAINT constraint_document_id IF NOT EXISTS FOR (d:SourceDocument) REQUIRE d.document_id IS UNIQUE")
            session.run("CREATE CONSTRAINT constraint_chunk_id IF NOT EXISTS FOR (c:DocumentChunk) REQUIRE c.chunk_id IS UNIQUE")
            session.run("CREATE CONSTRAINT constraint_work_item_id IF NOT EXISTS FOR (w:WorkItem) REQUIRE w.work_item_id IS UNIQUE")
            session.run("CREATE CONSTRAINT constraint_disbursement_id IF NOT EXISTS FOR (d:Disbursement) REQUIRE d.disbursement_id IS UNIQUE")
            session.run("CREATE CONSTRAINT constraint_fee_earner_id IF NOT EXISTS FOR (f:FeeEarner) REQUIRE f.fee_earner_id IS UNIQUE")
            console.print("[green]Created constraints[/green]")
        except Exception as e:
            console.print(f"[yellow]Note: Constraint creation failed (might already exist): {e}[/yellow]")

def create_default_records(driver):
    """Create default records for law firm and client party."""
    with driver.session() as session:
        # Create default law firm
        result = session.run("""
            MERGE (f:LawFirm {
                firm_id: '00000000-0000-0000-0000-000000000001',
                name: 'Default Law Firm',
                sra_number: '123456',
                address: '123 Legal Street, London, UK',
                vat_number: 'GB123456789',
                contact_email: 'info@defaultlawfirm.com'
            })
            RETURN f.firm_id as firm_id
        """)
        firm_id = result.single()["firm_id"]
        console.print("[green]Created default law firm[/green]")

        # Create default client party
        result = session.run("""
            MERGE (p:Party {
                party_id: '00000000-0000-0000-0000-000000000002',
                name: 'Default Client',
                role: 'Claimant',
                is_represented: true,
                solicitor_firm_name: 'Default Law Firm',
                is_client_party: true
            })
            RETURN p.party_id as party_id
        """)
        party_id = result.single()["party_id"]
        console.print("[green]Created default client party[/green]")

        return firm_id, party_id

def initialize_database():
    """Initialize Neo4j database with required indexes."""
    try:
        # Get Neo4j connection details from environment
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")

        if not password:
            console.print("[red]Error: NEO4J_PASSWORD environment variable not set[/red]")
            raise typer.Exit(1)

        # Connect to Neo4j
        driver = GraphDatabase.driver(uri, auth=(username, password))
        
        try:
            # Verify connection
            driver.verify_connectivity()
            console.print("[green]Connected to Neo4j[/green]")
            
            # Drop existing indexes and constraints
            drop_existing_indexes(driver)
            
            # Create indexes
            create_indexes(driver)
            
            # Create constraints
            create_constraints(driver)
            
            # Create default records
            firm_id, party_id = create_default_records(driver)
            console.print(f"[green]Default records created with IDs:[/green]")
            console.print(f"[green]Firm ID: {firm_id}[/green]")
            console.print(f"[green]Party ID: {party_id}[/green]")
            
        except ServiceUnavailable as e:
            console.print(f"[red]Error: Could not connect to Neo4j: {e}[/red]")
            raise typer.Exit(1)
        finally:
            driver.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def init():
    """Initialize the Neo4j database with required indexes and constraints."""
    initialize_database()

if __name__ == "__main__":
    app() 