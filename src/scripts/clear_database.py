from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

def clear_database():
    """Clear all data, indexes, and constraints from the Neo4j database."""
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    )

    try:
        with driver.session() as session:
            # Drop all constraints
            console.print("[yellow]Dropping constraints...[/yellow]")
            session.run("""
                CALL apoc.schema.assert({},{},true)
            """)
            
            # Drop all indexes
            console.print("[yellow]Dropping indexes...[/yellow]")
            session.run("""
                CALL apoc.schema.assert({},{},true)
            """)
            
            # Delete all relationships and nodes
            console.print("[yellow]Deleting all nodes and relationships...[/yellow]")
            result = session.run("""
                MATCH (n)
                DETACH DELETE n
            """)
            
            # Get the count of remaining nodes
            count_result = session.run("""
                MATCH (n)
                RETURN count(n) as count
            """)
            count = count_result.single()["count"]
            
            # Get remaining labels
            labels_result = session.run("""
                CALL db.labels()
                YIELD label
                RETURN collect(label) as labels
            """)
            labels = labels_result.single()["labels"]
            
            console.print("\n[green]Database cleared successfully![/green]")
            console.print(f"[green]Remaining nodes: {count}[/green]")
            if labels:
                console.print(f"[yellow]Remaining labels: {', '.join(labels)}[/yellow]")
            else:
                console.print("[green]No labels remaining[/green]")
            
    except Exception as e:
        console.print(f"[red]Error clearing database: {str(e)}[/red]")
        raise
    finally:
        driver.close()

if __name__ == "__main__":
    # Ask for confirmation
    console.print("[red]WARNING: This will clear ALL data, indexes, and constraints from the database![/red]")
    response = input("Are you sure you want to proceed? This cannot be undone! (yes/no): ")
    if response.lower() == 'yes':
        clear_database()
    else:
        console.print("[yellow]Operation cancelled.[/yellow]") 