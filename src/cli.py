"""Command-line interface for Fetch-Embed"""
import sys
import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from .service import MetadataService
from .utils.logger import setup_logger

console = Console()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    Fetch-Embed: High-quality EBook Metadata Fetching and Embedding Service

    Extracts metadata from ebook files, queries multiple API providers,
    uses fuzzy matching to find the best matches, and writes the improved
    metadata back to the files.
    """
    pass


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--config', '-c', type=click.Path(exists=True),
              help='Path to configuration file')
@click.option('--dry-run', '-n', is_flag=True,
              help='Show what would be done without making changes')
@click.option('--verbose', '-v', is_flag=True,
              help='Enable verbose logging')
@click.option('--output', '-o', type=click.Path(),
              help='Save processing report to JSON file')
def process(file_path: str, config: Optional[str], dry_run: bool,
           verbose: bool, output: Optional[str]):
    """
    Process a single ebook file to fetch and embed metadata

    FILE_PATH: Path to the ebook file to process
    """
    log_level = "DEBUG" if verbose else "INFO"

    try:
        with console.status("[bold green]Initializing service...") as status:
            service = MetadataService(config_path=config, log_level=log_level)

        console.print(f"\n[bold]Processing:[/bold] {Path(file_path).name}")

        if dry_run:
            console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=None)
            result = service.process_file(file_path, dry_run=dry_run)

        # Display results
        _display_result(result, dry_run)

        # Save output if requested
        if output:
            with open(output, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            console.print(f"\n[green]Report saved to:[/green] {output}")

        service.close()

        # Exit with appropriate code
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument('directory_path', type=click.Path(exists=True))
@click.option('--config', '-c', type=click.Path(exists=True),
              help='Path to configuration file')
@click.option('--recursive', '-r', is_flag=True, default=True,
              help='Process subdirectories recursively (default: True)')
@click.option('--dry-run', '-n', is_flag=True,
              help='Show what would be done without making changes')
@click.option('--verbose', '-v', is_flag=True,
              help='Enable verbose logging')
@click.option('--output', '-o', type=click.Path(),
              help='Save processing report to JSON file')
def batch(directory_path: str, config: Optional[str], recursive: bool,
         dry_run: bool, verbose: bool, output: Optional[str]):
    """
    Process all ebook files in a directory

    DIRECTORY_PATH: Path to directory containing ebook files
    """
    log_level = "DEBUG" if verbose else "INFO"

    try:
        with console.status("[bold green]Initializing service..."):
            service = MetadataService(config_path=config, log_level=log_level)

        console.print(f"\n[bold]Processing directory:[/bold] {directory_path}")
        console.print(f"[bold]Recursive:[/bold] {recursive}")

        if dry_run:
            console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

        results = service.process_directory(
            directory_path,
            recursive=recursive,
            dry_run=dry_run
        )

        # Display summary
        _display_batch_summary(results, dry_run)

        # Save output if requested
        if output:
            with open(output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            console.print(f"\n[green]Report saved to:[/green] {output}")

        service.close()

        # Exit with appropriate code
        successful = sum(1 for r in results if r['success'])
        sys.exit(0 if successful == len(results) else 1)

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--verbose', '-v', is_flag=True,
              help='Show detailed metadata')
def info(file_path: str, verbose: bool):
    """
    Display metadata information for an ebook file

    FILE_PATH: Path to the ebook file
    """
    try:
        from .extractors.factory import ExtractorFactory

        console.print(f"\n[bold]File:[/bold] {Path(file_path).name}\n")

        with console.status("[bold green]Extracting metadata..."):
            extractor = ExtractorFactory()
            metadata = extractor.extract_metadata(file_path)

        if not metadata:
            console.print("[red]Failed to extract metadata[/red]")
            sys.exit(1)

        # Display metadata
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Title", metadata.title or "[dim]Not set[/dim]")
        table.add_row("Authors", ", ".join(metadata.authors) if metadata.authors else "[dim]Not set[/dim]")
        table.add_row("ISBN", metadata.isbn or "[dim]Not set[/dim]")
        table.add_row("ISBN-13", metadata.isbn13 or "[dim]Not set[/dim]")
        table.add_row("Publisher", metadata.publisher or "[dim]Not set[/dim]")
        table.add_row("Published Date", metadata.published_date or "[dim]Not set[/dim]")
        table.add_row("Language", metadata.language or "[dim]Not set[/dim]")
        table.add_row("Pages", str(metadata.pages) if metadata.pages else "[dim]Not set[/dim]")
        table.add_row("Completeness", f"{metadata.metadata_completeness:.2%}")

        console.print(table)

        if verbose and metadata.description:
            console.print("\n[bold]Description:[/bold]")
            console.print(metadata.description[:500] + "..." if len(metadata.description) > 500 else metadata.description)

        if verbose and metadata.subjects:
            console.print("\n[bold]Subjects:[/bold]")
            console.print(", ".join(metadata.subjects[:10]))

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', type=click.Path(),
              default='config.yaml',
              help='Output path for configuration file')
def init_config(output: str):
    """
    Generate a default configuration file
    """
    try:
        from .utils.config import Config

        config = Config()
        config.save(output)

        console.print(f"[green]Configuration file created:[/green] {output}")
        console.print("\nEdit this file to customize API keys and settings.")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


def _display_result(result: dict, dry_run: bool):
    """Display processing result"""
    console.print("\n[bold]Results:[/bold]\n")

    # Original metadata
    original = result.get('original_metadata', {})
    console.print("[bold cyan]Original Metadata:[/bold cyan]")
    console.print(f"  Title: {original.get('title', 'None')}")
    console.print(f"  Authors: {', '.join(original.get('authors', [])) or 'None'}")
    console.print(f"  Completeness: {original.get('metadata_completeness', 0):.2%}\n")

    # API Results
    api_results = result.get('api_results', {})
    if api_results:
        total_results = sum(len(results) for results in api_results.values())
        console.print(f"[bold cyan]API Results:[/bold cyan] {total_results} results from {len(api_results)} sources")
        for source, results in api_results.items():
            console.print(f"  {source}: {len(results)} results")
        console.print()

    # Scored metadata
    scored = result.get('scored_metadata')
    if scored:
        console.print("[bold cyan]Best Match:[/bold cyan]")
        console.print(f"  Title: {scored['title']['value']} (confidence: {scored['title']['score']:.2%})")
        console.print(f"  Authors: {', '.join(scored['authors']['value'])} (confidence: {scored['authors']['score']:.2%})")
        console.print(f"  Overall Confidence: {scored['overall_confidence']:.2%}")
        console.print(f"  Sources: {', '.join(scored['sources'].keys())}\n")

    # Status
    if result['success']:
        if dry_run:
            console.print("[yellow]✓ Processing complete (dry run - no changes made)[/yellow]")
        elif result.get('metadata_written'):
            console.print("[green]✓ Metadata successfully updated[/green]")
        else:
            console.print("[green]✓ Processing complete[/green]")
    else:
        error = result.get('error', 'Unknown error')
        console.print(f"[red]✗ Processing failed: {error}[/red]")


def _display_batch_summary(results: list, dry_run: bool):
    """Display batch processing summary"""
    console.print("\n[bold]Summary:[/bold]\n")

    total = len(results)
    successful = sum(1 for r in results if r['success'])
    written = sum(1 for r in results if r.get('metadata_written', False))
    failed = total - successful

    # Statistics table
    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")

    table.add_row("Total Files", str(total))
    table.add_row("Successful", str(successful))
    if not dry_run:
        table.add_row("Updated", str(written))
    table.add_row("Failed", str(failed) if failed > 0 else "[green]0[/green]")

    console.print(table)

    # Show failed files if any
    if failed > 0:
        console.print("\n[bold red]Failed Files:[/bold red]")
        for result in results:
            if not result['success']:
                filename = Path(result['file_path']).name
                error = result.get('error', 'Unknown error')
                console.print(f"  • {filename}: {error}")


if __name__ == '__main__':
    cli()
