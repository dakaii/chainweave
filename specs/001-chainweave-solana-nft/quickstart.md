# ChainWeave Quickstart Guide

**Version**: 0.1.0 | **Last Updated**: September 8, 2025

## Overview
Quick development setup and validation guide for ChainWeave Solana NFT analytics platform.

## Prerequisites

### Required Tools
- Python 3.11+
- Google Cloud CLI (`gcloud`)
- Git
- Docker (optional for local containers)

### Required Accounts  
- Google Cloud Project with billing enabled
- Helius API account (free tier available)
- GitHub account for version control

### Environment Setup
```bash
# Clone repository
git clone <repository-url>
cd chainweave

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

## Local Development Setup

### 1. Configuration
Create environment configuration file:
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```bash
# Helius API
HELIUS_API_KEY=your_helius_api_key_here
HELIUS_WEBHOOK_URL=http://localhost:8000/webhook/helius

# Google Cloud Project
GCP_PROJECT_ID=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# BigQuery Configuration
BIGQUERY_DATASET=chainweave_dev
BIGQUERY_LOCATION=us-central1

# Pub/Sub Configuration  
PUBSUB_TOPIC=nft-events-dev
PUBSUB_SUBSCRIPTION=nft-processor-dev

# Dashboard Configuration
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
```

### 2. Google Cloud Setup
```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable bigquery.googleapis.com
gcloud services enable pubsub.googleapis.com  
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Create service account for local development
gcloud iam service-accounts create chainweave-dev \
    --description="ChainWeave development service account" \
    --display-name="ChainWeave Dev"

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:chainweave-dev@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:chainweave-dev@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/pubsub.admin"

# Create and download service account key
gcloud iam service-accounts keys create ./config/chainweave-dev-key.json \
    --iam-account=chainweave-dev@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 3. Initialize BigQuery
```bash
# Create dataset and tables
python scripts/setup_bigquery.py --project-id YOUR_PROJECT_ID --dataset chainweave_dev
```

### 4. Initialize Pub/Sub
```bash
# Create topic and subscription
python scripts/setup_pubsub.py --project-id YOUR_PROJECT_ID --env dev
```

## Running the Application

### Option 1: Individual Services
Start each service in separate terminal windows:

**Terminal 1 - Webhook Service:**
```bash
cd backend/webhook-service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Data Processor:**
```bash
cd backend/data-processor  
python -m chainweave.processor.main --subscription nft-processor-dev
```

**Terminal 3 - Dashboard:**
```bash
cd frontend/dashboard
streamlit run app.py --server.port 8501
```

### Option 2: Docker Compose (Recommended)
```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f webhook-service
docker-compose logs -f data-processor
docker-compose logs -f dashboard
```

## Validation & Testing

### 1. Health Checks
Verify all services are running:
```bash
# Webhook service
curl http://localhost:8000/health

# Dashboard
curl http://localhost:8501/health

# BigQuery connectivity
python scripts/test_bigquery.py --project-id YOUR_PROJECT_ID
```

### 2. End-to-End Test
Run complete pipeline test:
```bash
# Send test webhook payload
python scripts/test_webhook.py --url http://localhost:8000/webhook/helius

# Verify data in BigQuery
python scripts/verify_pipeline.py --project-id YOUR_PROJECT_ID --dataset chainweave_dev
```

### 3. Dashboard Access
Open dashboard in browser:
- URL: http://localhost:8501
- Should display collections overview with test data
- Navigate to whale tracking and attribute analysis sections

### 4. Run Test Suite
```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires running services)
pytest tests/integration/ -v

# Contract tests
pytest tests/contract/ -v

# Full test suite
pytest tests/ -v --cov=chainweave --cov-report=html
```

## Sample Data Setup

### Load Test Collections
```bash
# Load popular Solana NFT collections for testing
python scripts/load_sample_data.py \
    --collections "Mad Lads,DeGods,Okay Bears" \
    --days-back 7 \
    --project-id YOUR_PROJECT_ID
```

### Configure Test Webhooks
```bash
# Register webhook with Helius (requires API key)
python scripts/register_webhook.py \
    --webhook-url http://localhost:8000/webhook/helius \
    --collections "Mad Lads" \
    --api-key YOUR_HELIUS_API_KEY
```

## Troubleshooting

### Common Issues

**BigQuery Permission Errors:**
```bash
# Verify service account has correct permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
    --filter="bindings.members:chainweave-dev@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

**Pub/Sub Connection Issues:**
```bash
# Test Pub/Sub connectivity
python scripts/test_pubsub.py --project-id YOUR_PROJECT_ID --topic nft-events-dev
```

**Dashboard Not Loading:**
- Check Streamlit logs for BigQuery connection errors
- Verify GOOGLE_APPLICATION_CREDENTIALS path is correct
- Ensure dataset exists and has sample data

**Webhook Payload Validation Errors:**
- Check Helius webhook configuration matches expected schema
- Verify API key has correct permissions
- Review webhook service logs for detailed validation errors

### Log Locations
- Webhook Service: `logs/webhook-service.log`
- Data Processor: `logs/data-processor.log`  
- Dashboard: Streamlit outputs to console
- Test Results: `reports/test-results.html`

### Performance Monitoring
```bash
# Monitor BigQuery usage
python scripts/monitor_bigquery.py --project-id YOUR_PROJECT_ID

# Check Pub/Sub metrics
python scripts/monitor_pubsub.py --project-id YOUR_PROJECT_ID --subscription nft-processor-dev
```

## Next Steps

### Development Workflow
1. Create feature branch: `git checkout -b feature/new-analytics`
2. Write tests first following TDD principles
3. Implement feature with appropriate error handling
4. Run full test suite: `pytest tests/ -v`
5. Update documentation if needed
6. Create pull request with test results

### Deployment Preparation
1. Update version in `pyproject.toml`
2. Run security scan: `safety check`
3. Generate deployment artifacts: `python scripts/build_deployment.py`
4. Test in staging environment
5. Deploy via Pulumi: `pulumi up`

### Monitoring Setup
1. Configure BigQuery cost alerts
2. Set up Pub/Sub message monitoring
3. Create dashboard uptime checks
4. Enable Cloud Logging integration

---
**Success Criteria**: All health checks pass, test data loads correctly, and dashboard displays whale activity and collection analytics.

**Support**: Check logs first, then create GitHub issue with error details and environment information.