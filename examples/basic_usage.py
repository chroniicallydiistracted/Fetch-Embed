"""
Basic usage example for Fetch-Embed

This example demonstrates how to use the MetadataService programmatically
to fetch and embed metadata for ebook files.
"""

from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.service import MetadataService


def main():
    """Basic usage example"""

    # Initialize the service
    print("Initializing Fetch-Embed Metadata Service...")
    service = MetadataService(log_level="INFO")

    # Example 1: Process a single file
    print("\n" + "="*60)
    print("Example 1: Processing a single file")
    print("="*60)

    ebook_file = "path/to/your/ebook.epub"  # Replace with actual file path

    # Check if file exists
    if not Path(ebook_file).exists():
        print(f"File not found: {ebook_file}")
        print("Please update the path in this example script.")
    else:
        # Process the file
        result = service.process_file(ebook_file, dry_run=False)

        # Check result
        if result['success']:
            print("\n✓ Successfully processed file!")

            # Display statistics
            stats = service.get_statistics(result)
            print(f"\nStatistics:")
            print(f"  File: {stats['file']}")
            print(f"  API Sources: {stats['api_sources']}")
            print(f"  Total Results: {stats['total_api_results']}")
            print(f"  Confidence: {stats.get('overall_confidence', 0):.2%}")
            print(f"  Metadata Written: {stats['metadata_written']}")
        else:
            print(f"\n✗ Failed to process file: {result.get('error')}")

    # Example 2: Dry run mode
    print("\n" + "="*60)
    print("Example 2: Dry run mode (no changes)")
    print("="*60)

    if Path(ebook_file).exists():
        result = service.process_file(ebook_file, dry_run=True)

        print("\nDry run completed - no changes were made")
        print(f"Would have achieved {result.get('scored_metadata', {}).get('overall_confidence', 0):.2%} confidence")

    # Example 3: Process a directory
    print("\n" + "="*60)
    print("Example 3: Processing a directory")
    print("="*60)

    ebook_directory = "path/to/ebook/directory"  # Replace with actual directory

    if not Path(ebook_directory).exists():
        print(f"Directory not found: {ebook_directory}")
        print("Please update the path in this example script.")
    else:
        results = service.process_directory(
            ebook_directory,
            recursive=True,
            dry_run=True  # Use dry_run=False to actually write metadata
        )

        # Display summary
        successful = sum(1 for r in results if r['success'])
        print(f"\nProcessed {len(results)} files")
        print(f"Successful: {successful}/{len(results)}")

        # Show details for each file
        for result in results:
            filename = Path(result['file_path']).name
            status = "✓" if result['success'] else "✗"
            confidence = result.get('scored_metadata', {}).get('overall_confidence', 0)
            print(f"  {status} {filename}: {confidence:.2%} confidence")

    # Close the service
    service.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
