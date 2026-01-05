# Fetch-Embed

**An all-in-one, high-quality EBook Metadata Fetching and Embedding Service**

Fetch-Embed is a comprehensive tool that intelligently extracts, fetches, compares, and embeds accurate metadata into your ebook files. It queries multiple API services (Google Books, OpenLibrary, and more), uses advanced fuzzy matching and confidence scoring to find the best metadata matches, and seamlessly writes the improved metadata back to your files.

## ✨ Features

- 📚 **Multi-Format Support**: EPUB, MOBI, AZW3, PDF, and more
- 🔍 **Smart Metadata Extraction**: Reads existing metadata from ebook files
- 🌐 **Multiple API Providers**: Queries Google Books, OpenLibrary, and others
- 🎯 **Fuzzy Matching**: Uses advanced algorithms to match books even with incomplete data
- ⚖️ **Confidence Scoring**: Compares results from multiple sources and selects the best match for each field
- 📝 **Intelligent Fallback**: Uses filename as fuzzy search query if metadata is missing or poor quality
- 💾 **Safe Writing**: Uses Calibre's `ebook-meta` for maximum stability and format support
- 🔄 **Automatic Backups**: Creates backups before modifying files
- 🖥️ **CLI & Library**: Use as a command-line tool or Python library
- 📊 **Detailed Reporting**: Get comprehensive statistics and confidence scores

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+**
2. **Calibre** (for metadata writing)
   ```bash
   # Ubuntu/Debian
   sudo apt-get install calibre

   # macOS
   brew install calibre

   # Windows: Download from https://calibre-ebook.com/download
   ```

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Fetch-Embed.git
   cd Fetch-Embed
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) Install as a package:
   ```bash
   pip install -e .
   ```

4. (Optional) Set up API keys:
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

### Basic Usage

#### Command Line

Process a single file:
```bash
python fetch-embed.py process /path/to/book.epub
```

Process a directory:
```bash
python fetch-embed.py batch /path/to/ebooks --recursive
```

Dry run (see what would happen without making changes):
```bash
python fetch-embed.py process /path/to/book.epub --dry-run
```

View file metadata:
```bash
python fetch-embed.py info /path/to/book.epub
```

Generate configuration file:
```bash
python fetch-embed.py init-config
```

#### Python Library

```python
from src.service import MetadataService

# Initialize service
service = MetadataService()

# Process a single file
result = service.process_file('/path/to/book.epub')

if result['success']:
    print("Metadata updated successfully!")
    print(f"Confidence: {result['scored_metadata']['overall_confidence']:.2%}")

# Process a directory
results = service.process_directory('/path/to/ebooks', recursive=True)

# Clean up
service.close()
```

## 🔧 Configuration

Create a configuration file:
```bash
python fetch-embed.py init-config -o config.yaml
```

Key configuration options:

```yaml
api:
  google_books:
    enabled: true
    api_key: "your-api-key"  # Optional but recommended
    max_results: 5

  openlibrary:
    enabled: true
    max_results: 5

matching:
  title_weight: 0.4        # Weight for title matching
  author_weight: 0.3       # Weight for author matching
  isbn_weight: 0.3         # Weight for ISBN matching
  min_confidence_threshold: 0.6
  fuzzy_threshold: 80

processing:
  backup_original: true
  backup_dir: ".backups"
  use_filename_fallback: true
  overwrite_existing: true
```

## 📖 How It Works

Fetch-Embed follows a sophisticated 4-step process:

### 1. **Extract Existing Metadata**
   - Reads current metadata from the ebook file
   - Extracts title, authors, ISBN, publisher, etc.
   - Calculates metadata completeness score
   - Falls back to filename parsing if metadata is poor

### 2. **Query API Providers**
   - Searches Google Books API
   - Searches OpenLibrary API
   - Optionally searches ISBNdb (if configured)
   - Uses ISBN when available for precise matching
   - Uses title + author with fuzzy matching as fallback

### 3. **Score and Aggregate Results**
   - Compares each API result against original metadata
   - Calculates confidence scores based on:
     - Title similarity (fuzzy matching)
     - Author similarity (handles different formats)
     - ISBN exact matching
   - Aggregates best values from multiple sources
   - Uses consensus voting for fields like publisher
   - Selects longest/most detailed descriptions

### 4. **Write Metadata**
   - Uses Calibre's `ebook-meta` for maximum stability
   - Creates backup before modification
   - Writes improved metadata to file
   - Supports OPF file import/export

## 🎯 Fuzzy Matching Examples

Fetch-Embed excels at matching books even with incomplete or messy metadata:

| Original | API Result | Match Score |
|----------|-----------|-------------|
| "HarryPotter1" | "Harry Potter and the Philosopher's Stone" | 85% |
| "J.K. Rowling" | "Rowling, J.K." | 95% |
| "LOTR Fellowship" | "The Lord of the Rings: The Fellowship of the Ring" | 82% |

## 📊 Confidence Scoring

Each metadata field receives a confidence score (0-100%):

- **ISBN Match**: If ISBNs match exactly → Very high confidence
- **Title Match**: Fuzzy string matching with penalties for editions/subtitles
- **Author Match**: Handles different name formats (First Last, Last, First)
- **Consensus**: Multiple sources agreeing → Higher confidence
- **Overall Score**: Weighted average of all fields

Example output:
```
Best Match:
  Title: Harry Potter and the Philosopher's Stone (confidence: 95%)
  Authors: J.K. Rowling (confidence: 98%)
  Overall Confidence: 89%
  Sources: Google Books, OpenLibrary
```

## 🛡️ Safety Features

- **Automatic Backups**: Creates timestamped backups before modification
- **Dry Run Mode**: Preview changes without modifying files
- **Validation**: Checks file integrity before and after
- **Restore**: Automatically restores from backup if write fails
- **Calibre Integration**: Uses battle-tested metadata handling

## 📁 Project Structure

```
Fetch-Embed/
├── src/
│   ├── api_clients/       # API client implementations
│   │   ├── base.py
│   │   ├── google_books.py
│   │   ├── openlibrary.py
│   │   └── factory.py
│   ├── extractors/        # Metadata extraction
│   │   ├── base.py
│   │   ├── epub_extractor.py
│   │   ├── pdf_extractor.py
│   │   ├── mobi_extractor.py
│   │   └── factory.py
│   ├── matchers/          # Fuzzy matching & scoring
│   │   ├── fuzzy_matcher.py
│   │   └── confidence_scorer.py
│   ├── writers/           # Metadata writing
│   │   ├── base.py
│   │   ├── calibre_writer.py
│   │   ├── epub_writer.py
│   │   └── factory.py
│   ├── utils/             # Utilities
│   │   ├── config.py
│   │   └── logger.py
│   ├── service.py         # Main orchestrator
│   └── cli.py             # Command-line interface
├── examples/              # Example scripts
├── config/                # Configuration templates
├── tests/                 # Unit tests
├── requirements.txt
├── setup.py
└── README.md
```

## 🔌 API Providers

### Google Books API
- **Free** with optional API key for higher limits
- Very comprehensive metadata
- Get API key: https://console.cloud.google.com/apis/credentials

### OpenLibrary
- **Completely free**, no API key required
- Open-source book database
- Good coverage of older/classic books

### ISBNdb (Optional)
- Paid service
- Very accurate ISBN-based lookups
- Get API key: https://isbndb.com/

## 💡 Tips

1. **Always start with a dry run** to see what changes will be made:
   ```bash
   python fetch-embed.py process book.epub --dry-run
   ```

2. **Use verbose mode** for debugging:
   ```bash
   python fetch-embed.py process book.epub --verbose
   ```

3. **Books with ISBNs** get much better matches
4. **Clean filenames help** when metadata is missing
5. **Enable Google Books API key** for better rate limits
6. **Keep backups enabled** until you're confident in results

## 🐛 Troubleshooting

### "Calibre not found"
Install Calibre and ensure `ebook-meta` is in your PATH.

### "No API results"
- Check your internet connection
- Verify API keys in config/environment
- Try with a well-known book first

### "Low confidence scores"
- Check if the original metadata is very different from actual book
- Try with a book that has an ISBN
- Use verbose mode to see matching details

### "Metadata not written"
- Check file permissions
- Ensure file is not open in another program
- Check backup directory is writable

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Calibre**: For the excellent ebook-meta tool
- **Google Books API**: For comprehensive book metadata
- **OpenLibrary**: For their open book database
- **RapidFuzz**: For fast fuzzy string matching

## 📮 Support

If you encounter any issues or have questions:
- Open an issue on GitHub
- Check existing issues for solutions
- See examples/ directory for usage examples

---

**Made with ❤️ for ebook enthusiasts**
