# Old Mutual Zoho RAG System

[![CI](https://github.com/old-mutual-uganda/zoho-rag/workflows/CI/badge.svg)](https://github.com/old-mutual-uganda/zoho-rag/actions)
[![codecov](https://codecov.io/gh/old-mutual-uganda/zoho-rag/branch/main/graph/badge.svg)](https://codecov.io/gh/old-mutual-uganda/zoho-rag)

Hybrid RAG system for Old Mutual Uganda's Zoho ecosystem with conversational AI.

##  Quick Start

### Prerequisites
- Python 3.11+
- API Keys: OpenAI, Pinecone, Zoho
- 4GB+ RAM

### Installation
```bash
# Clone repository
git clone https://github.com/old-mutual-uganda/rag.git
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
# 1. Scrape data
python scripts/run_scraping.py --scrapers all

# 2. Process data
python scripts/process_data.py

# 3. Generate embeddings
python scripts/generate_embeddings.py \
  --chunks-file data/processed/processed_chunks_*.jsonl

# 4. Run RAG system
python scripts/run_rag.py
```

## 📚 Documentation

- [Setup Guide](docs/setup.md)
- [Architecture](docs/rag_architecture.md)
- [API Documentation](docs/api_documentation.md)
- [Contributing](CONTRIBUTING.md)

## 📊 Project Status

-  Data Scraping
-  Data Processing
-  Embedding Generation
-  RAG Pipeline
-  Zoho Integration
-  Production Deployment

## 🤝 Contact

