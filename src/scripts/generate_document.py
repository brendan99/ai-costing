#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import typer
from rich.console import Console
from rich.progress import Progress

# Add src directory to Python path
src_path = str(Path(__file__).parent.parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from src.models.domain import DocumentType
from src.generation.generator import DocumentGenerator
from src.graph.operations import Neo4jGraph

app = typer.Typer()
console = Console()

@app.command()
def generate(
    case_reference: str = typer.Argument(..., help="Case reference number"),
    document_type: DocumentType = typer.Argument(..., help="Type of document to generate"),
):
    """Generate a legal document for a case."""
    try:
        # Initialize components
        graph = Neo4jGraph()
        graph.connect()
        generator = DocumentGenerator()

        # Get case from Neo4j
        case = graph.get_case(case_reference)
        if not case:
            console.print(f"[red]Case not found: {case_reference}[/red]")
            raise typer.Exit(1)

        # Generate document
        with Progress() as progress:
            task = progress.add_task("[cyan]Generating document...", total=None)
            
            try:
                content = generator.generate_document(case.id, document_type)
                progress.update(task, completed=True)
                
                # Save document
                file_path = generator.save_document(content, case, document_type)
                console.print(f"[green]Document generated and saved to: {file_path}[/green]")
                
            except Exception as e:
                console.print(f"[red]Error generating document: {e}[/red]")
                raise

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        graph.close()

if __name__ == "__main__":
    app() 