# ChainWeave Data Processor

The data processor service bridges webhook events from Helius and transforms them into structured data for analytics.

## Features

- ✅ **Webhook Processing**: Processes Helius NFT transaction webhooks
- ✅ **Data Enrichment**: Enriches transactions with metadata from various sources
- ✅ **Whale Detection**: Identifies and alerts on high-value transactions
- ✅ **Collection Analytics**: Tracks collection metrics and trends
- ✅ **Wallet Profiling**: Builds wallet behavior profiles
- ✅ **BigQuery Integration**: Stores processed data in BigQuery for analytics
- ✅ **Local Development**: SQLite backend for local testing

## Architecture

```
Helius Webhook → Pub/Sub → Data Processor → BigQuery → Dashboard API
```

### Components

1. **Main Processor** (`app/main.py`): Production Pub/Sub subscriber
2. **Local Processor** (`src/local_processor.py`): SQLite-based development version
3. **Data Enrichment** (`../src/services/data_enrichment.py`): Metadata enrichment
4. **Whale Detector** (`../src/services/whale_detector.py`): High-value transaction detection
5. **Collection Analyzer** (`../src/services/collection_analyzer.py`): Collection metrics

## Quick Start

### Local Development

```bash
# Run local processor with test data
cd backend/data-processor
python tests/test_local_processor.py --mode test

# Run real-time simulation
python tests/test_local_processor.py --mode demo

# Run webhook bridge
python src/webhook_bridge.py
```

### Production

```bash
# Run with Pub/Sub (requires GCP setup)
python src/cli.py --log-level INFO

# Run with Docker
docker build -t chainweave-processor .
docker run chainweave-processor
```

## Configuration

Set environment variables:

```bash
# Google Cloud
export GCP_PROJECT_ID="your-project"
export BIGQUERY_DATASET="chainweave_prod"
export PUBSUB_SUBSCRIPTION="nft-processor"

# Helius API
export HELIUS_API_KEY="your-helius-key"

# Whale Detection
export WHALE_VOLUME_THRESHOLD_SOL="100.0"
export WHALE_ALERT_COOLDOWN_HOURS="6"
```

## Data Flow

1. **Webhook Reception**: Helius sends NFT transaction webhooks
2. **Message Queuing**: Events stored in Pub/Sub for reliable processing
3. **Data Processing**:
   - Extract transaction details
   - Enrich with metadata
   - Analyze for whale activity
   - Update collection metrics
   - Update wallet profiles
4. **Storage**: Processed data stored in BigQuery tables
5. **Analytics**: Dashboard API queries processed data

## Database Schema

### Transactions
- `transaction_signature` (PK)
- `mint_address`, `collection_id`
- `from_address`, `to_address`
- `price_sol`, `timestamp`
- `event_type`, `marketplace`

### Collections
- `collection_id` (PK)
- `name`, `symbol`, `total_supply`
- `floor_price`, `total_volume`
- `holder_count`, `created_at`

### Whale Alerts
- `alert_id` (PK)
- `wallet_address`, `alert_type`
- `amount_sol`, `severity`
- `triggered_at`, `details`

### Wallet Profiles
- `wallet_address` (PK)
- `first_seen`, `last_activity`
- `total_transactions`, `total_volume_traded`
- `whale_status`, `trading_behavior`

## Testing

```bash
# Unit tests
pytest tests/

# Local integration test
python tests/test_local_processor.py

# Load testing (simulate high volume)
python tests/test_local_processor.py --mode demo
```

## Monitoring

The processor provides:
- Structured JSON logging
- Processing statistics
- Health check endpoints
- Error tracking and alerting

## Deployment

### Local Development
1. Use SQLite backend via `LocalDataProcessor`
2. Generate mock data with test scripts
3. Monitor processing with local dashboard

### Production
1. Deploy to Cloud Run or Kubernetes
2. Configure Pub/Sub subscription
3. Set up BigQuery datasets
4. Configure monitoring and alerting

## Performance

- **Throughput**: 1000+ messages/minute
- **Latency**: <100ms per message
- **Reliability**: At-least-once delivery with Pub/Sub
- **Scalability**: Horizontal scaling with multiple instances