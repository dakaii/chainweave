# ChainWeave Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-09-08

## Active Technologies
- Python 3.11+ with FastAPI, Pandas, Streamlit
- Google Cloud Platform (BigQuery, Pub/Sub, Cloud Run)  
- Helius API for Solana blockchain data
- Pulumi (TypeScript) for infrastructure as code
- pytest for testing (001-chainweave-solana-nft)

## Project Structure
```
backend/
├── webhook-service/    # FastAPI Helius webhook receiver
├── data-processor/     # Pub/Sub consumer & BigQuery loader
└── tests/
frontend/
├── dashboard/          # Streamlit analytics dashboard  
└── tests/
infrastructure/
└── pulumi/            # GCP resource definitions
```

## Commands
# Development
pytest tests/ -v                    # Run all tests
streamlit run frontend/dashboard/app.py  # Start dashboard
uvicorn backend.webhook-service.main:app --reload  # Start webhook API

# Infrastructure  
pulumi up                           # Deploy to GCP
python scripts/setup_bigquery.py   # Initialize database schema

## Code Style
- Follow TDD: Tests before implementation (constitutional requirement)
- Use Pydantic for data validation
- JSON structured logging for GCP integration
- Real dependencies in tests (no mocks for BigQuery/Pub/Sub)

## Recent Changes
- 001-chainweave-solana-nft: Added Solana NFT analytics with whale tracking, collection heatmaps, attribute-price correlation

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->