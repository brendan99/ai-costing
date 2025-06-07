#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import typer
from rich.console import Console
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

app = typer.Typer()
console = Console()

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
                    `vector.dimensions`: 768,
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

@app.command()
def init():
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
            
            # Create indexes
            create_indexes(driver)
            
        except ServiceUnavailable as e:
            console.print(f"[red]Error: Could not connect to Neo4j: {e}[/red]")
            raise typer.Exit(1)
        finally:
            driver.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app() 