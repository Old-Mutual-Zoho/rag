# Website Scraper Usage Guide

## Production Script

The recommended way to run the scraper is using the production script:

```bash
# Activate virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# Run scraper with default config
python scripts/run_scraping.py

# Run with verbose output
python scripts/run_scraping.py --verbose

# Dry run (see what would be scraped without actually scraping)
python scripts/run_scraping.py --dry-run

# Custom configuration
python scripts/run_scraping.py --base-url https://example.com --output-dir data/custom

# Custom delay and retries
python scripts/run_scraping.py --delay 3.0 --max-retries 5

# Custom config file
python scripts/run_scraping.py --config config/custom_config.yml

# Custom log file
python scripts/run_scraping.py --log-file logs/my_scraper.log
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config` | Path to config YAML file | `config/scraping_config.yml` |
| `--base-url` | Base URL to scrape | From config |
| `--output-dir` | Output directory | From config |
| `--delay` | Delay between requests (seconds) | From config |
| `--max-retries` | Maximum retries | From config |
| `--verbose`, `-v` | Enable verbose logging | `False` |
| `--log-file` | Path to log file | `logs/scraper.log` |
| `--dry-run` | Dry run mode (no scraping) | `False` |

## Alternative: Direct Python Execution

You can also run the scraper directly from Python:

```python
from src.scrapers.website_scraper import OldMutualWebsiteScraper

# Initialize and run
scraper = OldMutualWebsiteScraper()
data = scraper.scrape()

print(f"Scraped {len(data)} pages")
```

Or use the module's `__main__`:

```bash
python -m src.scrapers.website_scraper
```

## Output

The scraper will:
1. Save data to `data/raw/website/website_scrape_YYYYMMDD_HHMMSS.json`
2. Log to `logs/scraper.log` (or specified log file)
3. Display statistics in the console

