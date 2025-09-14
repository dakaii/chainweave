# Tasks: ChainWeave - Solana NFT Analytics Platform

**Input**: Design documents from `/Users/dakaii/Workspace/projects/chainweave/specs/001-chainweave-solana-nft/`
**Prerequisites**: plan.md (✅), research.md (✅), data-model.md (✅), contracts/ (✅), quickstart.md (✅)

## Execution Flow (main)
```
1. Load plan.md from feature directory ✅
   → Tech stack: Python 3.11+, FastAPI, BigQuery, Pub/Sub, Streamlit, Pulumi
   → Structure: web app (backend + frontend)
2. Load optional design documents ✅
   → data-model.md: 6 entities (NFTCollection, NFTMetadata, Transaction, WalletProfile, WhaleAlert, MarketAnalytics)
   → contracts/: 2 API specs (webhook-api.yaml, dashboard-api.yaml)
   → quickstart.md: Setup and validation scenarios
3. Generate tasks by category ✅
4. Apply task rules: Different files [P], Tests before implementation ✅
5. Number tasks sequentially (T001, T002...) ✅
6. Generate dependency graph ✅
7. Create parallel execution examples ✅
8. Validate task completeness ✅
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Paths assume web app structure: `backend/` and `frontend/`

## Phase 3.1: Setup

- [ ] T001 Create project structure per implementation plan (backend/, frontend/, infrastructure/, scripts/, tests/)
- [ ] T002 Initialize Python project with FastAPI, BigQuery, Pub/Sub, Streamlit dependencies in requirements.txt
- [ ] T003 [P] Configure linting tools (black, isort, flake8) in pyproject.toml
- [ ] T004 [P] Setup environment configuration (.env.example, config.py)
- [ ] T005 [P] Initialize Pulumi TypeScript project in infrastructure/

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests [P] - Webhook API
- [ ] T006 [P] Contract test POST /webhook/helius in tests/contract/test_webhook_helius.py
- [ ] T007 [P] Contract test GET /health in tests/contract/test_webhook_health.py

### Contract Tests [P] - Dashboard API  
- [ ] T008 [P] Contract test GET /collections in tests/contract/test_dashboard_collections.py
- [ ] T009 [P] Contract test GET /collections/{id} in tests/contract/test_dashboard_collection_details.py
- [ ] T010 [P] Contract test GET /collections/{id}/heatmap in tests/contract/test_dashboard_heatmap.py
- [ ] T011 [P] Contract test GET /whales in tests/contract/test_dashboard_whales.py
- [ ] T012 [P] Contract test GET /wallets/{address} in tests/contract/test_dashboard_wallet.py
- [ ] T013 [P] Contract test POST /attributes/analysis in tests/contract/test_dashboard_attributes.py

### Integration Tests [P] - User Stories
- [ ] T014 [P] Integration test whale tracking feature in tests/integration/test_whale_tracking.py
- [ ] T015 [P] Integration test collection heatmap in tests/integration/test_collection_heatmap.py  
- [ ] T016 [P] Integration test attribute-price correlation in tests/integration/test_attribute_analysis.py
- [ ] T017 [P] End-to-end pipeline test (webhook → BigQuery → dashboard) in tests/integration/test_pipeline_e2e.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Data Models [P]
- [ ] T018 [P] NFTCollection Pydantic model in backend/src/models/nft_collection.py
- [ ] T019 [P] NFTMetadata Pydantic model in backend/src/models/nft_metadata.py
- [ ] T020 [P] Transaction Pydantic model in backend/src/models/transaction.py
- [ ] T021 [P] WalletProfile Pydantic model in backend/src/models/wallet_profile.py
- [ ] T022 [P] WhaleAlert Pydantic model in backend/src/models/whale_alert.py
- [ ] T023 [P] MarketAnalytics Pydantic model in backend/src/models/market_analytics.py

### BigQuery Schema [P]
- [ ] T024 [P] BigQuery table schemas in backend/src/schemas/bigquery_schemas.py
- [ ] T025 [P] Schema migration utilities in backend/src/schemas/migrations.py

### Libraries and Services
- [ ] T026 [P] chainweave-ingestion library CLI in backend/src/lib/ingestion/cli.py
- [ ] T027 [P] chainweave-analytics library CLI in backend/src/lib/analytics/cli.py  
- [ ] T028 [P] chainweave-dashboard library CLI in frontend/src/lib/dashboard/cli.py
- [ ] T029 Helius webhook validation service in backend/src/services/webhook_service.py
- [ ] T030 Pub/Sub publisher service in backend/src/services/pubsub_service.py
- [ ] T031 BigQuery data processor service in backend/src/services/data_processor.py
- [ ] T032 Whale detection service in backend/src/services/whale_service.py
- [ ] T033 Analytics aggregation service in backend/src/services/analytics_service.py

### API Endpoints - Webhook Service
- [ ] T034 POST /webhook/helius endpoint in backend/webhook-service/app/main.py
- [ ] T035 GET /health endpoint in backend/webhook-service/app/main.py

### API Endpoints - Dashboard Service  
- [ ] T036 GET /collections endpoint in backend/dashboard-service/app/main.py
- [ ] T037 GET /collections/{id} endpoint in backend/dashboard-service/app/main.py
- [ ] T038 GET /collections/{id}/heatmap endpoint in backend/dashboard-service/app/main.py
- [ ] T039 GET /whales endpoint in backend/dashboard-service/app/main.py
- [ ] T040 GET /wallets/{address} endpoint in backend/dashboard-service/app/main.py
- [ ] T041 POST /attributes/analysis endpoint in backend/dashboard-service/app/main.py

### Dashboard Frontend
- [ ] T042 Collections overview page in frontend/dashboard/pages/collections.py
- [ ] T043 Whale tracking page in frontend/dashboard/pages/whales.py
- [ ] T044 Collection heatmap visualization in frontend/dashboard/components/heatmap.py
- [ ] T045 Attribute analysis page in frontend/dashboard/pages/attributes.py
- [ ] T046 Wallet profile page in frontend/dashboard/pages/wallet.py

## Phase 3.4: Infrastructure & Integration

### Cloud Infrastructure
- [ ] T047 Pulumi GCP resources (Cloud Run, Pub/Sub, BigQuery) in infrastructure/main.ts
- [ ] T048 BigQuery dataset and table creation in scripts/setup_bigquery.py
- [ ] T049 Pub/Sub topic and subscription setup in scripts/setup_pubsub.py
- [ ] T050 Service account and IAM permissions in infrastructure/iam.ts

### Data Pipeline Integration
- [ ] T051 Connect webhook service to Pub/Sub publisher in backend/webhook-service/app/main.py
- [ ] T052 Connect data processor to Pub/Sub subscriber in backend/data-processor/main.py
- [ ] T053 Connect dashboard service to BigQuery client in backend/dashboard-service/app/bigquery_client.py
- [ ] T054 Error handling and dead letter queue setup in backend/src/services/error_handler.py

### Observability & Monitoring
- [ ] T055 [P] Structured JSON logging setup in backend/src/utils/logging.py
- [ ] T056 [P] Cloud Monitoring integration in backend/src/utils/monitoring.py
- [ ] T057 [P] Request tracing and correlation IDs in backend/src/middleware/tracing.py

## Phase 3.5: Polish & Validation

### Unit Tests [P]
- [ ] T058 [P] Unit tests for Pydantic models in tests/unit/test_models.py
- [ ] T059 [P] Unit tests for webhook validation in tests/unit/test_webhook_validation.py  
- [ ] T060 [P] Unit tests for whale detection logic in tests/unit/test_whale_detection.py
- [ ] T061 [P] Unit tests for attribute correlation in tests/unit/test_attribute_correlation.py

### Performance & Optimization
- [ ] T062 BigQuery query optimization and partitioning validation
- [ ] T063 Dashboard response time optimization (<2s target)
- [ ] T064 Pub/Sub message throughput testing

### Documentation & Deployment
- [ ] T065 [P] Library documentation in llms.txt format for each lib
- [ ] T066 [P] API documentation generation from OpenAPI specs  
- [ ] T067 [P] Deployment scripts and CI/CD pipeline setup
- [ ] T068 Execute quickstart validation scenarios from quickstart.md

## Dependencies

**Sequential Blocks**:
- Setup (T001-T005) → Tests (T006-T017) → Implementation (T018-T057) → Polish (T058-T068)
- Models (T018-T025) must complete before Services (T029-T033)
- Services complete before Endpoints (T034-T041) 
- Infrastructure (T047-T050) before Integration (T051-T054)

**Key Blocking Relationships**:
- T024 (BigQuery schemas) blocks T031, T048, T053
- T029-T033 (Services) block T034-T041 (Endpoints)
- T047 (Infrastructure) blocks T051-T053 (Integration)

## Parallel Execution Examples

### Phase 3.2 - All Contract Tests Together:
```bash
# Launch T006-T013 together (all contract tests):
Task: "Contract test POST /webhook/helius in tests/contract/test_webhook_helius.py"
Task: "Contract test GET /health in tests/contract/test_webhook_health.py"  
Task: "Contract test GET /collections in tests/contract/test_dashboard_collections.py"
Task: "Contract test GET /collections/{id} in tests/contract/test_dashboard_collection_details.py"
Task: "Contract test GET /collections/{id}/heatmap in tests/contract/test_dashboard_heatmap.py"
Task: "Contract test GET /whales in tests/contract/test_dashboard_whales.py"
Task: "Contract test GET /wallets/{address} in tests/contract/test_dashboard_wallet.py"
Task: "Contract test POST /attributes/analysis in tests/contract/test_dashboard_attributes.py"
```

### Phase 3.3 - All Data Models Together:
```bash
# Launch T018-T023 together (all Pydantic models):
Task: "NFTCollection Pydantic model in backend/src/models/nft_collection.py"
Task: "NFTMetadata Pydantic model in backend/src/models/nft_metadata.py"
Task: "Transaction Pydantic model in backend/src/models/transaction.py"
Task: "WalletProfile Pydantic model in backend/src/models/wallet_profile.py"
Task: "WhaleAlert Pydantic model in backend/src/models/whale_alert.py"  
Task: "MarketAnalytics Pydantic model in backend/src/models/market_analytics.py"
```

### Phase 3.3 - All Library CLIs Together:
```bash
# Launch T026-T028 together (library CLIs):
Task: "chainweave-ingestion library CLI in backend/src/lib/ingestion/cli.py"
Task: "chainweave-analytics library CLI in backend/src/lib/analytics/cli.py"
Task: "chainweave-dashboard library CLI in frontend/src/lib/dashboard/cli.py"
```

## Notes
- **[P] tasks** = different files, no shared dependencies
- **TDD Critical**: Verify all contract and integration tests fail before implementing T018+
- **Constitutional**: Each library must have CLI with --help, --version, --format
- **BigQuery**: Use real BigQuery instance in integration tests, not mocks
- **Free Tier**: Monitor GCP usage throughout implementation
- **Error Handling**: Implement comprehensive error logging for production debugging

## Task Generation Rules Applied

1. **From Contracts**: ✅
   - webhook-api.yaml → 2 contract test tasks (T006-T007)
   - dashboard-api.yaml → 6 contract test tasks (T008-T013)
   
2. **From Data Model**: ✅
   - 6 entities → 6 model creation tasks [P] (T018-T023)
   - BigQuery schemas → schema tasks (T024-T025)
   
3. **From User Stories**: ✅
   - Whale tracking → integration test (T014)
   - Collection heatmaps → integration test (T015) 
   - Attribute analysis → integration test (T016)
   - End-to-end → pipeline test (T017)

4. **From Architecture**: ✅
   - 3 libraries → 3 CLI tasks [P] (T026-T028)
   - Services → implementation tasks (T029-T033)
   - Infrastructure → Pulumi + GCP setup (T047-T050)

## Validation Checklist
*GATE: All items verified before task execution*

- [x] All contracts have corresponding tests (T006-T013 cover both APIs)
- [x] All entities have model tasks (T018-T023 cover 6 entities)
- [x] All tests come before implementation (Phase 3.2 before 3.3)
- [x] Parallel tasks truly independent (different files, marked [P])
- [x] Each task specifies exact file path
- [x] No task modifies same file as another [P] task
- [x] Constitutional requirements addressed (TDD, libraries, CLIs, real dependencies)

**Total Tasks**: 68 tasks across 5 phases
**Parallel Opportunities**: 23 tasks can run in parallel across 8 groups
**Estimated Completion**: 28-32 implementation tasks as planned in Phase 2

---
*Ready for execution - all tasks are specific enough for LLM completion*