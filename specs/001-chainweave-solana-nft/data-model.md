# Data Model: ChainWeave

**Phase 1 Output** | Generated: September 8, 2025

## Overview
Core data entities for ChainWeave Solana NFT analytics platform, designed for BigQuery storage and real-time analytics queries.

## Entity Relationships

```
Collection (1) ←→ (N) NFTMetadata ←→ (N) Transaction
    ↓                    ↓                ↓
    ├─ MarketAnalytics   ├─ WalletProfile  └─ WhaleAlert
    └─ CollectionStats   └─ OwnershipHistory
```

## Core Entities

### NFTCollection
Primary grouping entity for related NFTs, typically from same creator or project.

**Fields**:
- `collection_id`: STRING (Primary Key) - Unique identifier
- `collection_address`: STRING - On-chain collection address  
- `name`: STRING - Human-readable collection name
- `symbol`: STRING - Trading symbol/ticker
- `creator_address`: STRING - Original creator wallet
- `total_supply`: INTEGER - Maximum possible NFTs in collection
- `created_at`: TIMESTAMP - First mint timestamp
- `updated_at`: TIMESTAMP - Last metadata update
- `floor_price`: FLOAT - Current lowest listing price in SOL
- `total_volume`: FLOAT - All-time trading volume in SOL

**Validation Rules**:
- collection_address must be valid Solana address format
- total_supply > 0
- creator_address must be valid Solana address format
- floor_price >= 0 (can be 0 for no active listings)

**State Transitions**: 
- Created → Active (first NFT minted)
- Active → Completed (total_supply reached)
- Any → Inactive (no trading activity for 90 days)

### NFTMetadata  
Individual NFT characteristics and current ownership information.

**Fields**:
- `mint_address`: STRING (Primary Key) - Unique NFT identifier
- `collection_id`: STRING (Foreign Key) - Links to NFTCollection
- `name`: STRING - Individual NFT name
- `image_url`: STRING - IPFS or HTTP link to artwork
- `attributes`: JSON - Trait/rarity data as key-value pairs
- `rarity_rank`: INTEGER - Rank within collection (1 = rarest)
- `rarity_score`: FLOAT - Calculated rarity score
- `current_owner`: STRING - Current holder wallet address
- `mint_timestamp`: TIMESTAMP - When NFT was first created
- `last_transfer`: TIMESTAMP - Most recent ownership change

**Validation Rules**:
- mint_address must be valid Solana mint address
- collection_id must exist in NFTCollection table
- attributes JSON must be valid format
- rarity_rank between 1 and collection total_supply
- current_owner must be valid Solana address

**Relationships**:
- Many-to-One with NFTCollection
- One-to-Many with Transaction (via mint_address)

### Transaction
Individual NFT transfer, sale, or mint events from blockchain.

**Fields**:
- `transaction_signature`: STRING (Primary Key) - Solana transaction hash
- `mint_address`: STRING (Foreign Key) - NFT being transferred
- `event_type`: STRING - ENUM: ['mint', 'transfer', 'sale', 'burn']
- `from_address`: STRING - Sender wallet (null for mint events)
- `to_address`: STRING - Recipient wallet (null for burn events)
- `price_sol`: FLOAT - Sale price in SOL (null for non-sale events)
- `price_usd`: FLOAT - USD equivalent at transaction time
- `marketplace`: STRING - Platform facilitating sale (Magic Eden, OpenSea, etc.)
- `timestamp`: TIMESTAMP - Block timestamp
- `block_height`: INTEGER - Solana block number
- `instruction_index`: INTEGER - Position within transaction

**Validation Rules**:
- transaction_signature must be unique and valid format
- mint_address must exist in NFTMetadata table  
- event_type must be valid enum value
- For sales: price_sol > 0 and marketplace required
- For transfers: from_address and to_address both required
- For mints: from_address null, to_address required
- timestamp must be realistic (after 2020, not future)

**State Transitions**:
- Created → Confirmed (included in finalized block)
- Any → Failed (transaction reverted)

### WalletProfile
Aggregated analytics and behavior patterns for individual wallets.

**Fields**:
- `wallet_address`: STRING (Primary Key) - Solana wallet address
- `total_nfts_owned`: INTEGER - Current NFT count across all collections
- `total_volume_traded`: FLOAT - Lifetime trading volume in SOL
- `first_activity`: TIMESTAMP - First recorded transaction
- `last_activity`: TIMESTAMP - Most recent transaction
- `avg_hold_duration`: INTEGER - Average days holding NFTs before sale
- `collections_active`: INTEGER - Number of different collections traded
- `whale_status`: BOOLEAN - Meets high-volume trader criteria
- `profit_loss_sol`: FLOAT - Estimated P&L from completed trades
- `favorite_marketplace`: STRING - Most frequently used trading platform

**Validation Rules**:
- wallet_address must be valid Solana address format
- total_nfts_owned >= 0
- total_volume_traded >= 0
- first_activity <= last_activity
- collections_active >= 0

**Calculated Fields** (updated via scheduled queries):
- profit_loss_sol = SUM(sale_price - purchase_price) for closed positions
- avg_hold_duration = AVG(sale_timestamp - purchase_timestamp)
- whale_status = total_volume_traded > WHALE_THRESHOLD OR total_nfts_owned > WHALE_COUNT

### WhaleAlert
Significant trading events that meet predefined criteria for tracking.

**Fields**:
- `alert_id`: STRING (Primary Key) - Generated UUID
- `transaction_signature`: STRING (Foreign Key) - Related transaction
- `wallet_address`: STRING (Foreign Key) - Wallet triggering alert
- `alert_type`: STRING - ENUM: ['large_purchase', 'large_sale', 'whale_mint', 'collection_sweep']
- `nft_count`: INTEGER - Number of NFTs in transaction
- `total_value_sol`: FLOAT - Combined value in SOL
- `collection_id`: STRING (Foreign Key) - Affected collection
- `triggered_at`: TIMESTAMP - When alert criteria were met
- `notification_sent`: BOOLEAN - Whether alert was distributed

**Validation Rules**:
- transaction_signature must exist in Transaction table
- wallet_address must exist in WalletProfile table
- alert_type must be valid enum value
- nft_count > 0
- total_value_sol >= alert threshold for type

### MarketAnalytics
Pre-calculated aggregations for dashboard performance optimization.

**Fields**:
- `metric_id`: STRING (Primary Key) - Composite key: {collection_id}_{date}_{metric_type}
- `collection_id`: STRING (Foreign Key) - Collection being measured
- `date`: DATE - Aggregation date
- `metric_type`: STRING - ENUM: ['daily_volume', 'unique_traders', 'avg_price', 'holders_count']
- `metric_value`: FLOAT - Calculated metric value
- `created_at`: TIMESTAMP - When aggregation was computed

**Validation Rules**:
- collection_id must exist in NFTCollection table
- date must be valid date format
- metric_type must be valid enum value
- metric_value >= 0

## BigQuery Schema Considerations

### Partitioning Strategy
- **Transaction**: Partition by DATE(timestamp) for time-based queries
- **WhaleAlert**: Partition by DATE(triggered_at) for recent activity focus
- **MarketAnalytics**: Partition by date for efficient time-series queries

### Clustering Strategy
- **Transaction**: Cluster by [mint_address, event_type] for NFT history queries
- **NFTMetadata**: Cluster by [collection_id, current_owner] for ownership queries
- **WalletProfile**: Cluster by [whale_status, last_activity] for whale tracking

### Indexing Requirements
- **NFTCollection**: Index on [creator_address, created_at]
- **Transaction**: Index on [from_address, to_address, timestamp]
- **WalletProfile**: Index on [total_volume_traded, whale_status]

## Data Lineage

### Source Data Flow
```
Helius Webhook → FastAPI Validation → Pub/Sub → Cloud Function Transform → BigQuery Load
```

### Transformation Rules
1. **Price Normalization**: Convert all prices to consistent SOL and USD values
2. **Address Validation**: Verify all Solana addresses using base58 encoding
3. **Timestamp Standardization**: UTC timestamps for all time fields
4. **Attribute Parsing**: Normalize JSON metadata into queryable format
5. **Duplicate Prevention**: Use transaction_signature as idempotency key

### Update Patterns
- **NFTMetadata**: Update current_owner and last_transfer on ownership change
- **WalletProfile**: Recalculate metrics nightly via scheduled BigQuery jobs
- **MarketAnalytics**: Generate daily aggregations at 00:00 UTC
- **WhaleAlert**: Real-time generation on transaction ingestion

## Quality Assurance

### Data Validation
- Schema enforcement at BigQuery load time
- Foreign key relationships validated via Cloud Functions
- Duplicate detection using composite keys and timestamps
- Data quality monitoring with Cloud Logging alerts

### Consistency Checks
- Total supply vs. minted NFT count reconciliation
- Wallet balance vs. owned NFT count validation  
- Transaction volume vs. collection volume aggregation verification
- Cross-reference marketplace APIs for price validation

---
*Data model complete - ready for contract generation*