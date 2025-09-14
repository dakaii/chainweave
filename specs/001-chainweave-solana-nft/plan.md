# Implementation Plan: ChainWeave - Solana NFT Analytics Platform

**Branch**: `001-chainweave-solana-nft` | **Date**: September 8, 2025 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/Users/dakaii/Workspace/projects/chainweave/specs/001-chainweave-solana-nft/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
4. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
5. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, or `GEMINI.md` for Gemini CLI).
6. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
7. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
8. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
ChainWeave is a real-time Solana NFT analytics platform that ingests blockchain data via Helius webhooks, processes it through a data pipeline, and provides interactive dashboards for whale tracking, collection heatmaps, and attribute-price correlation analysis. Built as a cloud-native data engineering showcase deployed on GCP within free tier limits.

## Technical Context
**Language/Version**: Python 3.11+ (FastAPI, Pandas processing)  
**Primary Dependencies**: FastAPI, Helius API, Google Cloud libraries, Streamlit, Pandas  
**Storage**: BigQuery (primary analytics) or CloudSQL (alternative), Pub/Sub (message queue)  
**Testing**: pytest (unit/integration), contract testing for APIs  
**Target Platform**: Google Cloud Platform (Cloud Run containers, managed services)
**Project Type**: web (data pipeline + dashboard frontend)  
**Performance Goals**: Handle webhook bursts, <2s dashboard response, real-time data updates  
**Constraints**: GCP free tier quotas, cost optimization, serverless scaling  
**Scale/Scope**: Multiple NFT collections, concurrent dashboard users, historical data retention

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: 3 (webhook-ingester, data-processor, dashboard) ✅
- Using framework directly? Yes - FastAPI, Streamlit without wrappers ✅
- Single data model? Yes - shared schemas for NFT/Transaction/Wallet entities ✅
- Avoiding patterns? Direct service calls, no unnecessary abstractions ✅

**Architecture**:
- EVERY feature as library? Yes - ingestion-lib, analytics-lib, dashboard-lib ✅
- Libraries listed: 
  - chainweave-ingestion: Helius webhook processing + Pub/Sub publishing
  - chainweave-analytics: BigQuery data processing + aggregations  
  - chainweave-dashboard: Streamlit UI components + visualization
- CLI per library: Each with --help/--version/--format support ✅
- Library docs: llms.txt format planned for each lib ✅

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor cycle enforced? Yes - contract tests fail first ✅
- Git commits show tests before implementation? Yes - TDD workflow ✅
- Order: Contract→Integration→E2E→Unit strictly followed? Yes ✅
- Real dependencies used? Yes - actual BigQuery/Pub/Sub in tests ✅
- Integration tests for: webhook contracts, data schemas, dashboard APIs ✅
- FORBIDDEN: Implementation before test, skipping RED phase ✅

**Observability**:
- Structured logging included? Yes - JSON logging for GCP integration ✅
- Frontend logs → backend? Yes - centralized Cloud Logging ✅
- Error context sufficient? Yes - request IDs, error details ✅

**Versioning**:
- Version number assigned? v0.1.0 (initial) ✅
- BUILD increments on every change? Yes - automated versioning ✅
- Breaking changes handled? Yes - API versioning strategy ✅

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure]
```

**Structure Decision**: Option 2 (Web application) - separate backend data pipeline and frontend dashboard

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `/scripts/update-agent-context.sh [claude|gemini|copilot]` for your AI assistant
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach  
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Contract-driven development:
  - webhook-api.yaml → webhook service contract tests [P]
  - dashboard-api.yaml → dashboard service contract tests [P]
- Data model implementation:
  - Each BigQuery entity → Pydantic model + schema creation [P]
  - NFTCollection, NFTMetadata, Transaction, WalletProfile, WhaleAlert, MarketAnalytics
- User story validation:
  - Whale tracking integration test (FR-002)
  - Collection heatmap visualization test (FR-003) 
  - Attribute-price correlation test (FR-004)
- Infrastructure setup:
  - Pulumi GCP resource provisioning
  - BigQuery dataset and table creation
  - Pub/Sub topic and subscription setup

**Ordering Strategy**:
- TDD constitutional order: Contract tests → Integration tests → Unit tests → Implementation
- Dependency order: Infrastructure → Data models → Services → Dashboard
- Parallel execution groups:
  - [P1] Contract test creation (independent API specs)
  - [P2] Pydantic model implementation (independent entities)  
  - [P3] Service implementation (after models complete)
  - [P4] Dashboard components (after service APIs)

**Estimated Output**: 28-32 numbered, ordered tasks in tasks.md
- 4 infrastructure tasks (Pulumi, BigQuery, Pub/Sub, monitoring)
- 8 contract test tasks (2 APIs × 4 endpoints each)
- 6 data model tasks (6 entities)
- 6 integration test tasks (user story scenarios)
- 4 service implementation tasks (webhook, processor, dashboard, analytics)
- 4 deployment/validation tasks

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)  
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS  
- [x] All NEEDS CLARIFICATION resolved (no unknowns remaining)
- [x] Complexity deviations documented (none required)

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*