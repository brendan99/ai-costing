#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import typer
from rich.console import Console
from rich.progress import Progress
from datetime import datetime
import uuid

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from src.models.domain import Case
from src.document.processor import DocumentProcessor
from src.graph.operations import Neo4jGraph

app = typer.Typer()
console = Console()

@app.command()
def ingest(
    case_reference: str = typer.Argument(..., help="Case reference number"),
    case_title: str = typer.Argument(..., help="Case title"),
    documents_dir: Path = typer.Argument(..., help="Directory containing case documents"),
    court: str = typer.Option(None, help="Court name"),
    description: str = typer.Option(None, help="Case description"),
):
    """Ingest case documents into the system."""
    try:
        # Initialize components
        graph = Neo4jGraph()
        graph.connect()
        processor = DocumentProcessor()

        # Create case
        case = Case(
            id=str(uuid.uuid4()),
            reference=case_reference,
            title=case_title,
            court=court,
            description=description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Store case in Neo4j
        case_id = graph.create_case(case)
        console.print(f"[green]Created case: {case_reference}[/green]")

        # Process documents
        with Progress() as progress:
            task = progress.add_task("[cyan]Processing documents...", total=None)
            
            try:
                chunks = processor.process_directory(str(documents_dir), case)
                progress.update(task, completed=True)
                
                console.print(f"[green]Successfully processed {len(chunks)} document chunks[/green]")
                
            except Exception as e:
                console.print(f"[red]Error processing documents: {e}[/red]")
                raise

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        graph.close()

if __name__ == "__main__":
    app() 