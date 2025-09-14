"""BigQuery table schemas for ChainWeave data warehouse.

This module defines the BigQuery table schemas that correspond to our Pydantic models.
Implements partitioning, clustering, and indexing strategies for optimal performance.
"""

from google.cloud import bigquery
from typing import List, Dict, Any
import json

class ChainWeaveBigQuerySchemas:
    """Central configuration for all ChainWeave BigQuery table schemas."""
    
    @staticmethod
    def get_nft_collections_schema() -> List[bigquery.SchemaField]:
        """Schema for NFT collections table."""
        return [
            bigquery.SchemaField("collection_id", "STRING", mode="REQUIRED", 
                                description="Unique collection identifier"),
            bigquery.SchemaField("collection_address", "STRING", mode="REQUIRED",
                                description="Solana collection mint address"),
            bigquery.SchemaField("name", "STRING", mode="REQUIRED",
                                description="Collection display name"),
            bigquery.SchemaField("symbol", "STRING", mode="NULLABLE",
                                description="Collection ticker symbol"),
            bigquery.SchemaField("description", "STRING", mode="NULLABLE",
                                description="Collection description"),
            bigquery.SchemaField("image_url", "STRING", mode="NULLABLE",
                                description="Collection artwork URL"),
            bigquery.SchemaField("creator_address", "STRING", mode="REQUIRED",
                                description="Creator wallet address"),
            bigquery.SchemaField("total_supply", "INTEGER", mode="REQUIRED",
                                description="Total NFTs in collection"),
            bigquery.SchemaField("verified", "BOOLEAN", mode="REQUIRED",
                                description="Official verification status"),
            bigquery.SchemaField("floor_price", "FLOAT", mode="NULLABLE",
                                description="Current floor price in SOL"),
            bigquery.SchemaField("market_cap", "FLOAT", mode="NULLABLE",
                                description="Total market value in SOL"),
            bigquery.SchemaField("volume_24h", "FLOAT", mode="NULLABLE",
                                description="24h trading volume in SOL"),
            bigquery.SchemaField("holders_count", "INTEGER", mode="NULLABLE",
                                description="Number of unique holders"),
            bigquery.SchemaField("listed_count", "INTEGER", mode="NULLABLE",
                                description="Number of NFTs currently listed"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED",
                                description="Collection lifecycle status"),
            bigquery.SchemaField("mint_date", "TIMESTAMP", mode="NULLABLE",
                                description="Collection launch date"),
            bigquery.SchemaField("last_sale", "TIMESTAMP", mode="NULLABLE",
                                description="Most recent sale timestamp"),
            bigquery.SchemaField("is_whale_tracked", "BOOLEAN", mode="REQUIRED",
                                description="Whether collection is tracked for whale activity"),
            bigquery.SchemaField("royalty_percentage", "FLOAT", mode="NULLABLE",
                                description="Creator royalty percentage"),
            bigquery.SchemaField("external_url", "STRING", mode="NULLABLE",
                                description="Official collection website"),
            bigquery.SchemaField("twitter_handle", "STRING", mode="NULLABLE",
                                description="Official Twitter handle"),
            bigquery.SchemaField("discord_url", "STRING", mode="NULLABLE",
                                description="Official Discord server"),
            bigquery.SchemaField("categories", "STRING", mode="REPEATED",
                                description="Collection categories/tags"),
            bigquery.SchemaField("attributes_schema", "JSON", mode="NULLABLE",
                                description="Trait types and possible values"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED",
                                description="When record was ingested"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED",
                                description="Last update timestamp"),
            bigquery.SchemaField("partition_date", "DATE", mode="REQUIRED",
                                description="Partitioning column")
        ]
    
    @staticmethod
    def get_nft_metadata_schema() -> List[bigquery.SchemaField]:
        """Schema for NFT metadata table."""
        return [
            bigquery.SchemaField("mint_address", "STRING", mode="REQUIRED",
                                description="Unique NFT mint address"),
            bigquery.SchemaField("collection_id", "STRING", mode="REQUIRED",
                                description="Parent collection identifier"),
            bigquery.SchemaField("name", "STRING", mode="REQUIRED",
                                description="Individual NFT name"),
            bigquery.SchemaField("image_url", "STRING", mode="REQUIRED",
                                description="NFT artwork URL"),
            bigquery.SchemaField("attributes", "JSON", mode="REQUIRED",
                                description="Trait/rarity data as JSON"),
            bigquery.SchemaField("rarity_rank", "INTEGER", mode="REQUIRED",
                                description="Rarity rank within collection"),
            bigquery.SchemaField("rarity_score", "FLOAT", mode="REQUIRED",
                                description="Calculated rarity score"),
            bigquery.SchemaField("current_owner", "STRING", mode="REQUIRED",
                                description="Current holder wallet address"),
            bigquery.SchemaField("mint_timestamp", "TIMESTAMP", mode="REQUIRED",
                                description="NFT creation timestamp"),
            bigquery.SchemaField("last_transfer", "TIMESTAMP", mode="REQUIRED",
                                description="Most recent ownership change"),
            bigquery.SchemaField("description", "STRING", mode="NULLABLE",
                                description="NFT description"),
            bigquery.SchemaField("external_url", "STRING", mode="NULLABLE",
                                description="External link for NFT"),
            bigquery.SchemaField("animation_url", "STRING", mode="NULLABLE",
                                description="Animation or video URL"),
            bigquery.SchemaField("hold_duration_days", "INTEGER", mode="NULLABLE",
                                description="Days since last transfer"),
            bigquery.SchemaField("estimated_value", "FLOAT", mode="NULLABLE",
                                description="Estimated current value in SOL"),
            bigquery.SchemaField("last_sale_price", "FLOAT", mode="NULLABLE",
                                description="Last known sale price in SOL"),
            bigquery.SchemaField("listing_price", "FLOAT", mode="NULLABLE",
                                description="Current listing price in SOL"),
            bigquery.SchemaField("is_listed", "BOOLEAN", mode="REQUIRED",
                                description="Whether NFT is currently listed"),
            bigquery.SchemaField("marketplace", "STRING", mode="NULLABLE",
                                description="Marketplace where NFT is listed"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED",
                                description="When record was ingested"),
            bigquery.SchemaField("partition_date", "DATE", mode="REQUIRED",
                                description="Partitioning column")
        ]
    
    @staticmethod
    def get_transactions_schema() -> List[bigquery.SchemaField]:
        """Schema for transactions table."""
        return [
            bigquery.SchemaField("transaction_signature", "STRING", mode="REQUIRED",
                                description="Solana transaction hash"),
            bigquery.SchemaField("mint_address", "STRING", mode="REQUIRED",
                                description="NFT being transferred"),
            bigquery.SchemaField("event_type", "STRING", mode="REQUIRED",
                                description="Type of blockchain event"),
            bigquery.SchemaField("from_address", "STRING", mode="NULLABLE",
                                description="Sender wallet address"),
            bigquery.SchemaField("to_address", "STRING", mode="NULLABLE",
                                description="Recipient wallet address"),
            bigquery.SchemaField("price_sol", "FLOAT", mode="NULLABLE",
                                description="Sale price in SOL"),
            bigquery.SchemaField("price_usd", "FLOAT", mode="NULLABLE",
                                description="USD equivalent at transaction time"),
            bigquery.SchemaField("marketplace", "STRING", mode="NULLABLE",
                                description="Platform facilitating sale"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED",
                                description="Block timestamp"),
            bigquery.SchemaField("block_height", "INTEGER", mode="REQUIRED",
                                description="Solana block number"),
            bigquery.SchemaField("instruction_index", "INTEGER", mode="NULLABLE",
                                description="Position within transaction"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED",
                                description="Transaction processing status"),
            bigquery.SchemaField("program_id", "STRING", mode="NULLABLE",
                                description="Solana program that executed transaction"),
            bigquery.SchemaField("collection_id", "STRING", mode="NULLABLE",
                                description="Associated collection identifier"),
            bigquery.SchemaField("royalty_paid", "FLOAT", mode="NULLABLE",
                                description="Creator royalty amount in SOL"),
            bigquery.SchemaField("marketplace_fee", "FLOAT", mode="NULLABLE",
                                description="Marketplace fee in SOL"),
            bigquery.SchemaField("gas_fee", "FLOAT", mode="NULLABLE",
                                description="Transaction fee in SOL"),
            bigquery.SchemaField("webhook_timestamp", "TIMESTAMP", mode="NULLABLE",
                                description="When webhook was received"),
            bigquery.SchemaField("slot_number", "INTEGER", mode="NULLABLE",
                                description="Solana slot number"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED",
                                description="When record was ingested"),
            bigquery.SchemaField("partition_date", "DATE", mode="REQUIRED",
                                description="Partitioning column based on timestamp")
        ]
    
    @staticmethod
    def get_wallet_profiles_schema() -> List[bigquery.SchemaField]:
        """Schema for wallet profiles table."""
        return [
            bigquery.SchemaField("wallet_address", "STRING", mode="REQUIRED",
                                description="Solana wallet address"),
            bigquery.SchemaField("total_nfts_owned", "INTEGER", mode="REQUIRED",
                                description="Current NFT count across collections"),
            bigquery.SchemaField("total_volume_traded", "FLOAT", mode="REQUIRED",
                                description="Lifetime trading volume in SOL"),
            bigquery.SchemaField("first_activity", "TIMESTAMP", mode="REQUIRED",
                                description="First recorded transaction"),
            bigquery.SchemaField("last_activity", "TIMESTAMP", mode="REQUIRED",
                                description="Most recent transaction"),
            bigquery.SchemaField("avg_hold_duration", "INTEGER", mode="REQUIRED",
                                description="Average days holding NFTs"),
            bigquery.SchemaField("collections_active", "INTEGER", mode="REQUIRED",
                                description="Number of collections traded"),
            bigquery.SchemaField("whale_status", "BOOLEAN", mode="REQUIRED",
                                description="High-volume trader status"),
            bigquery.SchemaField("profit_loss_sol", "FLOAT", mode="REQUIRED",
                                description="Estimated P&L from trades"),
            bigquery.SchemaField("favorite_marketplace", "STRING", mode="NULLABLE",
                                description="Most used trading platform"),
            bigquery.SchemaField("wallet_tier", "STRING", mode="REQUIRED",
                                description="Wallet classification tier"),
            bigquery.SchemaField("trading_behavior", "STRING", mode="REQUIRED",
                                description="Primary trading behavior pattern"),
            bigquery.SchemaField("total_spent_sol", "FLOAT", mode="REQUIRED",
                                description="Total SOL spent on purchases"),
            bigquery.SchemaField("total_received_sol", "FLOAT", mode="REQUIRED",
                                description="Total SOL received from sales"),
            bigquery.SchemaField("total_transactions", "INTEGER", mode="REQUIRED",
                                description="Total NFT transactions"),
            bigquery.SchemaField("successful_flips", "INTEGER", mode="REQUIRED",
                                description="Number of profitable sales"),
            bigquery.SchemaField("failed_flips", "INTEGER", mode="REQUIRED",
                                description="Number of unprofitable sales"),
            bigquery.SchemaField("avg_purchase_price", "FLOAT", mode="NULLABLE",
                                description="Average purchase price in SOL"),
            bigquery.SchemaField("avg_sale_price", "FLOAT", mode="NULLABLE",
                                description="Average sale price in SOL"),
            bigquery.SchemaField("largest_purchase_sol", "FLOAT", mode="NULLABLE",
                                description="Largest single purchase in SOL"),
            bigquery.SchemaField("largest_sale_sol", "FLOAT", mode="NULLABLE",
                                description="Largest single sale in SOL"),
            bigquery.SchemaField("win_rate", "FLOAT", mode="NULLABLE",
                                description="Percentage of profitable sales"),
            bigquery.SchemaField("days_active", "INTEGER", mode="NULLABLE",
                                description="Total days with NFT activity"),
            bigquery.SchemaField("avg_transactions_per_day", "FLOAT", mode="NULLABLE",
                                description="Average transactions per active day"),
            bigquery.SchemaField("most_active_hour", "INTEGER", mode="NULLABLE",
                                description="Hour of day with most activity"),
            bigquery.SchemaField("top_collection", "STRING", mode="NULLABLE",
                                description="Collection with most NFTs owned"),
            bigquery.SchemaField("portfolio_diversity_score", "FLOAT", mode="NULLABLE",
                                description="Portfolio diversification score"),
            bigquery.SchemaField("unique_counterparties", "INTEGER", mode="NULLABLE",
                                description="Number of unique trading partners"),
            bigquery.SchemaField("profile_updated_at", "TIMESTAMP", mode="REQUIRED",
                                description="Last profile calculation timestamp"),
            bigquery.SchemaField("partition_date", "DATE", mode="REQUIRED",
                                description="Partitioning column")
        ]
    
    @staticmethod
    def get_whale_alerts_schema() -> List[bigquery.SchemaField]:
        """Schema for whale alerts table."""
        return [
            bigquery.SchemaField("alert_id", "STRING", mode="REQUIRED",
                                description="Unique alert identifier"),
            bigquery.SchemaField("wallet_address", "STRING", mode="REQUIRED",
                                description="Wallet that triggered alert"),
            bigquery.SchemaField("alert_type", "STRING", mode="REQUIRED",
                                description="Type of whale activity detected"),
            bigquery.SchemaField("transaction_signature", "STRING", mode="NULLABLE",
                                description="Related transaction hash"),
            bigquery.SchemaField("collection_id", "STRING", mode="NULLABLE",
                                description="Affected collection"),
            bigquery.SchemaField("mint_address", "STRING", mode="NULLABLE",
                                description="Specific NFT involved"),
            bigquery.SchemaField("amount_sol", "FLOAT", mode="NULLABLE",
                                description="Transaction amount in SOL"),
            bigquery.SchemaField("severity", "STRING", mode="REQUIRED",
                                description="Alert severity level"),
            bigquery.SchemaField("triggered_at", "TIMESTAMP", mode="REQUIRED",
                                description="When alert was triggered"),
            bigquery.SchemaField("details", "JSON", mode="NULLABLE",
                                description="Additional alert context"),
            bigquery.SchemaField("resolved", "BOOLEAN", mode="REQUIRED",
                                description="Whether alert has been resolved"),
            bigquery.SchemaField("resolved_at", "TIMESTAMP", mode="NULLABLE",
                                description="When alert was resolved"),
            bigquery.SchemaField("resolution_reason", "STRING", mode="NULLABLE",
                                description="Why alert was resolved"),
            bigquery.SchemaField("notification_sent", "BOOLEAN", mode="REQUIRED",
                                description="Whether notification was dispatched"),
            bigquery.SchemaField("notification_channels", "STRING", mode="REPEATED",
                                description="Channels where alert was sent"),
            bigquery.SchemaField("cooldown_until", "TIMESTAMP", mode="NULLABLE",
                                description="When similar alerts can trigger again"),
            bigquery.SchemaField("market_impact_score", "FLOAT", mode="NULLABLE",
                                description="Estimated market impact"),
            bigquery.SchemaField("is_false_positive", "BOOLEAN", mode="REQUIRED",
                                description="Whether alert was false positive"),
            bigquery.SchemaField("feedback_score", "INTEGER", mode="NULLABLE",
                                description="User feedback on alert relevance"),
            bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED",
                                description="When record was ingested"),
            bigquery.SchemaField("partition_date", "DATE", mode="REQUIRED",
                                description="Partitioning column based on triggered_at")
        ]
    
    @staticmethod
    def get_market_analytics_schema() -> List[bigquery.SchemaField]:
        """Schema for market analytics table."""
        return [
            bigquery.SchemaField("metric_id", "STRING", mode="REQUIRED",
                                description="Composite key for metric"),
            bigquery.SchemaField("collection_id", "STRING", mode="NULLABLE",
                                description="Collection being measured"),
            bigquery.SchemaField("date", "DATE", mode="REQUIRED",
                                description="Aggregation date"),
            bigquery.SchemaField("metric_type", "STRING", mode="REQUIRED",
                                description="Type of metric being measured"),
            bigquery.SchemaField("metric_value", "FLOAT", mode="REQUIRED",
                                description="Calculated metric value"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED",
                                description="When aggregation was computed"),
            bigquery.SchemaField("granularity", "STRING", mode="REQUIRED",
                                description="Time granularity of metric"),
            bigquery.SchemaField("previous_value", "FLOAT", mode="NULLABLE",
                                description="Previous period value for comparison"),
            bigquery.SchemaField("change_percentage", "FLOAT", mode="NULLABLE",
                                description="Percentage change from previous period"),
            bigquery.SchemaField("sample_size", "INTEGER", mode="NULLABLE",
                                description="Number of data points used"),
            bigquery.SchemaField("confidence_score", "FLOAT", mode="NULLABLE",
                                description="Statistical confidence in metric"),
            bigquery.SchemaField("metric_metadata", "JSON", mode="NULLABLE",
                                description="Additional context for calculation"),
            bigquery.SchemaField("data_completeness", "FLOAT", mode="NULLABLE",
                                description="Completeness of underlying data"),
            bigquery.SchemaField("outliers_detected", "BOOLEAN", mode="REQUIRED",
                                description="Whether outliers were detected"),
            bigquery.SchemaField("calculation_method", "STRING", mode="NULLABLE",
                                description="Method used for calculation"),
            bigquery.SchemaField("partition_date", "DATE", mode="REQUIRED",
                                description="Partitioning column based on date")
        ]


class BigQueryTableConfig:
    """Configuration for BigQuery table creation and management."""
    
    @staticmethod
    def get_table_configs() -> Dict[str, Dict[str, Any]]:
        """Get complete table configuration including partitioning and clustering."""
        return {
            "nft_collections": {
                "schema": ChainWeaveBigQuerySchemas.get_nft_collections_schema(),
                "partition_field": "partition_date",
                "partition_type": bigquery.TimePartitioningType.DAY,
                "clustering_fields": ["collection_id", "status", "verified"],
                "description": "NFT collection master data with metadata and statistics"
            },
            "nft_metadata": {
                "schema": ChainWeaveBigQuerySchemas.get_nft_metadata_schema(),
                "partition_field": "partition_date", 
                "partition_type": bigquery.TimePartitioningType.DAY,
                "clustering_fields": ["collection_id", "current_owner", "is_listed"],
                "description": "Individual NFT metadata, ownership, and listing information"
            },
            "transactions": {
                "schema": ChainWeaveBigQuerySchemas.get_transactions_schema(),
                "partition_field": "partition_date",
                "partition_type": bigquery.TimePartitioningType.DAY,
                "clustering_fields": ["event_type", "collection_id", "marketplace"],
                "description": "NFT transaction events from blockchain"
            },
            "wallet_profiles": {
                "schema": ChainWeaveBigQuerySchemas.get_wallet_profiles_schema(),
                "partition_field": "partition_date",
                "partition_type": bigquery.TimePartitioningType.DAY,
                "clustering_fields": ["wallet_tier", "whale_status", "trading_behavior"],
                "description": "Aggregated wallet analytics and trading profiles"
            },
            "whale_alerts": {
                "schema": ChainWeaveBigQuerySchemas.get_whale_alerts_schema(),
                "partition_field": "partition_date",
                "partition_type": bigquery.TimePartitioningType.DAY,
                "clustering_fields": ["alert_type", "severity", "resolved"],
                "description": "Whale activity alerts and notifications"
            },
            "market_analytics": {
                "schema": ChainWeaveBigQuerySchemas.get_market_analytics_schema(),
                "partition_field": "partition_date",
                "partition_type": bigquery.TimePartitioningType.DAY,
                "clustering_fields": ["metric_type", "collection_id", "granularity"],
                "description": "Pre-calculated market analytics and dashboard metrics"
            }
        }


# SQL DDL templates for table creation
TABLE_CREATE_TEMPLATE = """
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.{table_name}` (
{field_definitions}
)
PARTITION BY {partition_field}
CLUSTER BY {clustering_fields}
OPTIONS(
  description="{description}",
  require_partition_filter=true
);
"""

# View definitions for common queries
ANALYTICS_VIEWS = {
    "daily_collection_stats": """
    CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.daily_collection_stats` AS
    SELECT 
      collection_id,
      date,
      SUM(CASE WHEN metric_type = 'daily_volume' THEN metric_value END) as volume_sol,
      SUM(CASE WHEN metric_type = 'unique_traders' THEN metric_value END) as unique_traders,
      AVG(CASE WHEN metric_type = 'floor_price' THEN metric_value END) as floor_price,
      SUM(CASE WHEN metric_type = 'total_sales' THEN metric_value END) as total_sales
    FROM `{project_id}.{dataset_id}.market_analytics`
    WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    GROUP BY collection_id, date
    ORDER BY date DESC, volume_sol DESC;
    """,
    
    "whale_activity_summary": """
    CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.whale_activity_summary` AS
    SELECT
      w.wallet_address,
      wp.wallet_tier,
      COUNT(*) as total_alerts,
      SUM(CASE WHEN w.severity = 'high' THEN 1 ELSE 0 END) as high_severity_alerts,
      SUM(w.amount_sol) as total_volume_sol,
      MAX(w.triggered_at) as last_alert,
      AVG(w.market_impact_score) as avg_market_impact
    FROM `{project_id}.{dataset_id}.whale_alerts` w
    LEFT JOIN `{project_id}.{dataset_id}.wallet_profiles` wp 
      ON w.wallet_address = wp.wallet_address
    WHERE w.partition_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    GROUP BY w.wallet_address, wp.wallet_tier
    ORDER BY total_volume_sol DESC;
    """,
    
    "collection_performance": """
    CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.collection_performance` AS
    SELECT
      c.collection_id,
      c.name,
      c.floor_price,
      c.volume_24h,
      c.holders_count,
      COALESCE(t.daily_transactions, 0) as daily_transactions,
      COALESCE(t.daily_volume, 0) as daily_volume,
      COALESCE(a.whale_alerts, 0) as whale_alerts_today
    FROM `{project_id}.{dataset_id}.nft_collections` c
    LEFT JOIN (
      SELECT 
        collection_id,
        COUNT(*) as daily_transactions,
        SUM(price_sol) as daily_volume
      FROM `{project_id}.{dataset_id}.transactions`
      WHERE partition_date = CURRENT_DATE()
        AND event_type = 'sale'
      GROUP BY collection_id
    ) t ON c.collection_id = t.collection_id
    LEFT JOIN (
      SELECT
        collection_id,
        COUNT(*) as whale_alerts
      FROM `{project_id}.{dataset_id}.whale_alerts`
      WHERE partition_date = CURRENT_DATE()
      GROUP BY collection_id
    ) a ON c.collection_id = a.collection_id
    WHERE c.partition_date = CURRENT_DATE()
    ORDER BY c.volume_24h DESC;
    """
}