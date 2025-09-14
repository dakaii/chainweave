# Research & Technology Decisions: ChainWeave

**Phase 0 Output** | Generated: September 8, 2025

## Overview
Research decisions for ChainWeave Solana NFT analytics platform, focusing on GCP deployment within free tier constraints and real-time data processing capabilities.

## Technology Decisions

### Data Ingestion Strategy
**Decision**: Helius Webhooks → Cloud Run FastAPI service
**Rationale**: 
- Helius provides reliable, real-time Solana event streaming with parsed transaction data
- Webhooks eliminate need for continuous blockchain polling, reducing costs
- Cloud Run scales to zero, fitting free tier constraints
- FastAPI provides async processing for webhook bursts

**Alternatives Considered**:
- Direct Solana RPC polling: Higher compute costs, rate limiting issues
- WebSocket connections: Persistent connections exceed free tier limits
- Shyft API: Similar functionality but less comprehensive parsed data

### Message Queue Architecture  
**Decision**: Google Cloud Pub/Sub
**Rationale**:
- Native GCP integration with IAM and monitoring
- 10GB/month free tier allowance sufficient for NFT events
- Decouples webhook ingestion from data processing
- Built-in dead letter queue support for reliability

**Alternatives Considered**:
- Apache Kafka: Over-complex for single-topic use case, no managed free option
- Redis Streams: Additional infrastructure management overhead
- Direct database writes: No fault tolerance for burst traffic

### Data Storage Strategy
**Decision**: BigQuery as primary analytics store
**Rationale**:
- 1TB/month free query allowance ideal for analytics workload
- 10GB free storage for historical data
- Native JSON support for blockchain transaction data
- SQL interface enables complex analytical queries
- Automatic scaling and partitioning

**Alternatives Considered**:
- CloudSQL PostgreSQL: Limited free tier (1GB), requires manual scaling
- Firestore: Not optimized for analytical queries and aggregations
- Cloud Storage + BigQuery External Tables: Query costs on full dataset

### Data Processing Pipeline
**Decision**: Python with Pandas + Google Cloud Functions
**Rationale**:
- Pandas excellent for NFT metadata normalization and enrichment
- Cloud Functions serverless execution within free tier (2M invocations)
- Python ecosystem strong for blockchain data processing
- Native BigQuery client library integration

**Alternatives Considered**:
- Apache Beam/Dataflow: Overkill for single-stream processing, higher costs
- Node.js processing: Limited data manipulation libraries compared to Python
- Streaming inserts: Higher costs than batch processing

### Dashboard & Visualization
**Decision**: Streamlit deployed on Cloud Run
**Rationale**:
- Rapid dashboard development with Python data science stack
- Direct BigQuery integration for real-time queries
- Cloud Run free tier sufficient for demo/portfolio usage
- Built-in authentication and sharing capabilities

**Alternatives Considered**:
- Custom React/Next.js frontend: Development time vs. portfolio timeline
- Metabase/Superset: Additional infrastructure management complexity
- Google Data Studio: Limited customization for specific NFT analytics

### Infrastructure as Code
**Decision**: Pulumi with TypeScript
**Rationale**:
- Type-safe infrastructure definitions reduce deployment errors
- Superior GCP resource coverage compared to Terraform
- Familiar syntax for JavaScript/TypeScript developers
- Excellent CI/CD integration capabilities

**Alternatives Considered**:
- Terraform: Less intuitive syntax, slower development iteration
- Google Deployment Manager: Limited community support and examples
- Manual GCP Console: Not repeatable or version controlled

### Authentication & Security
**Decision**: Anonymous access with optional wallet connection
**Rationale**:
- Portfolio demonstration doesn't require user management complexity
- Wallet connection adds Web3 authenticity without backend user storage
- Reduces infrastructure complexity and compliance requirements

**Alternatives Considered**:
- Full user registration system: Adds database requirements and complexity
- Google OAuth integration: Not necessary for public analytics dashboard
- API key authentication: Creates friction for public portfolio demonstration

### Data Retention Policy  
**Decision**: 90-day rolling window for detailed data, indefinite aggregates
**Rationale**:
- Balances analytical capability with free tier storage limits
- Daily/weekly/monthly aggregates provide long-term trending
- Raw transaction data sufficient for most NFT trading analysis timeframes

**Alternatives Considered**:
- Indefinite retention: Exceeds free tier storage limits over time
- 30-day window: Too short for meaningful seasonal analysis
- Archive to Cloud Storage: Adds complexity without clear portfolio benefit

### Performance Targets & Scaling
**Decision**: Support 50 concurrent users, <2s dashboard response
**Rationale**:
- Realistic for portfolio demonstration and small user base
- BigQuery performance sufficient for target response times
- Cloud Run autoscaling handles traffic bursts within free tier

**Alternatives Considered**:
- Higher concurrent users: Would exceed free tier limits
- Sub-second response times: Requires caching layer, added complexity

## Integration Patterns

### Webhook Processing Pattern
```
Helius Webhook → FastAPI Validation → Pub/Sub Publish → Cloud Function Transform → BigQuery Load
```

### Analytics Query Pattern  
```
Streamlit Dashboard → BigQuery Client → SQL Query → Pandas DataFrame → Visualization
```

### Error Handling Pattern
```
Failed Messages → Pub/Sub Dead Letter Topic → Cloud Function Retry → Alert/Manual Review
```

## Risk Mitigation

### Free Tier Limits
- **Risk**: Exceeding GCP quotas
- **Mitigation**: Monitoring alerts at 80% usage, graceful degradation
- **Fallback**: Local development environment for continued work

### Data Quality
- **Risk**: Malformed webhook data causing pipeline failures
- **Mitigation**: Strict Pydantic validation, comprehensive error logging
- **Fallback**: Dead letter queue for manual inspection and reprocessing

### Blockchain Dependency
- **Risk**: Helius service unavailability  
- **Mitigation**: Exponential backoff retry logic, status page monitoring
- **Fallback**: Switch to direct Solana RPC with rate limiting

## Success Criteria Validation

All technology decisions align with portfolio objectives:
- ✅ **Data Engineering Skills**: End-to-end pipeline with ingestion, transformation, storage
- ✅ **Solana Integration**: Native blockchain data processing without smart contracts  
- ✅ **GCP Deployment**: Full cloud-native architecture with IaC
- ✅ **Cost Optimization**: Designed for free tier operation with monitoring
- ✅ **Scalability Demo**: Serverless architecture shows understanding of cloud scaling

## Next Phase Requirements

Phase 1 (Design & Contracts) requires:
1. Data models for NFT entities (Collection, Transaction, Wallet, Metadata)
2. API contracts for webhook ingestion and dashboard queries
3. BigQuery table schemas with partitioning strategy
4. Integration test scenarios for each pipeline component
5. Quickstart guide for local development and GCP deployment

---
*Research complete - ready for Phase 1 design activities*