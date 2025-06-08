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

from src.models.domain import LegalCase
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
        processor = DocumentProcessor(graph)

        # Check if case exists
        existing_case = graph.find_case_by_reference(case_reference)
        if existing_case:
            console.print(f"[yellow]Found existing case: {case_reference}[/yellow]")
            case = existing_case
        else:
            console.print(f"[red]No case found with reference: {case_reference}[/red]")
            console.print("Please create the case first using the UI or case management system.")
            raise typer.Exit(1)

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