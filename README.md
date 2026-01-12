# Old Mutual Zoho RAG System
Hybrid RAG system for Old Mutual Uganda's Zoho ecosystem with conversational AI.

##  Quick Start

### Prerequisites
- Python 3.11+
- API Keys: OpenAI, Pinecone, Zoho
- 4GB+ RAM

### Installation
```bash
# Clone repository
git clone https://github.com/Old-Mutual-Zoho/rag.git
cd rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Initialize data directories
mkdir -p data/raw/{website,pdfs,zoho_exports}
mkdir -p data/processed logs
```

### Usage
```bash
# Activate virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# 1. Scrape data
python scripts/run_scraping.py

# Or with options:
python scripts/run_scraping.py --verbose
python scripts/run_scraping.py --dry-run  # Preview what will be scraped
python scripts/run_scraping.py --help     # See all options

# 2. Process data
python scripts/process_data.py

# 3. Generate embeddings
python scripts/generate_embeddings.py \
  --chunks-file data/processed/processed_chunks_*.jsonl

# 4. Run RAG system
python scripts/run_rag.py
```

## 📚 Documentation
- [Contributing](CONTRIBUTING.md)
- [Exploring scraping](SCRAPER_USAGE.md)


##  Contact

