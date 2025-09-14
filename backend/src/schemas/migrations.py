"""BigQuery schema migration utilities for ChainWeave.

This module provides utilities for creating, updating, and managing BigQuery tables
with proper error handling, rollback capabilities, and schema evolution support.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from google.cloud import bigquery
from google.cloud.exceptions import NotFound, Conflict
from datetime import datetime
import json

from .bigquery_schemas import BigQueryTableConfig, ChainWeaveBigQuerySchemas, ANALYTICS_VIEWS

logger = logging.getLogger(__name__)


class SchemaEvolution:
    """Handles schema evolution and backwards compatibility."""
    
    # Schema version history for each table
    SCHEMA_VERSIONS = {
        "nft_collections": {
            "v1.0": "2024-01-01",  # Initial schema
            "v1.1": "2024-02-01",  # Added social media fields
            "v1.2": "2024-03-01",  # Added whale tracking flag
        },
        "transactions": {
            "v1.0": "2024-01-01",  # Initial schema
            "v1.1": "2024-01-15",  # Added webhook metadata
        },
        "wallet_profiles": {
            "v1.0": "2024-01-01",  # Initial schema
            "v1.1": "2024-02-15",  # Added advanced analytics fields
        },
        "whale_alerts": {
            "v1.0": "2024-01-01",  # Initial schema
        },
        "market_analytics": {
            "v1.0": "2024-01-01",  # Initial schema
        },
        "nft_metadata": {
            "v1.0": "2024-01-01",  # Initial schema
        }
    }
    
    @classmethod
    def get_schema_changes(cls, table_name: str, from_version: str, to_version: str) -> List[Dict[str, Any]]:
        """Get list of schema changes needed to migrate between versions."""
        changes = []
        
        # This would contain actual migration logic for each version
        # For now, providing structure for future implementations
        if table_name == "nft_collections":
            if from_version == "v1.0" and to_version >= "v1.1":
                changes.extend([
                    {
                        "action": "add_field",
                        "field": bigquery.SchemaField("twitter_handle", "STRING", mode="NULLABLE"),
                        "description": "Add Twitter handle field"
                    },
                    {
                        "action": "add_field", 
                        "field": bigquery.SchemaField("discord_url", "STRING", mode="NULLABLE"),
                        "description": "Add Discord URL field"
                    }
                ])
        
        return changes


class BigQueryMigrationManager:
    """Manages BigQuery table creation, updates, and schema migrations."""
    
    def __init__(self, project_id: str, dataset_id: str, location: str = "US"):
        """Initialize migration manager with BigQuery client."""
        self.client = bigquery.Client(project=project_id)
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.location = location
        self.dataset_ref = self.client.dataset(dataset_id)
        
        # Ensure dataset exists
        self._ensure_dataset_exists()
    
    def _ensure_dataset_exists(self) -> None:
        """Create dataset if it doesn't exist."""
        try:
            self.client.get_dataset(self.dataset_ref)
            logger.info(f"Dataset {self.dataset_id} already exists")
        except NotFound:
            dataset = bigquery.Dataset(self.dataset_ref)
            dataset.location = self.location
            dataset.description = "ChainWeave NFT analytics data warehouse"
            
            # Set default table expiration (optional)
            # dataset.default_table_expiration_ms = 365 * 24 * 60 * 60 * 1000  # 1 year
            
            dataset = self.client.create_dataset(dataset, timeout=30)
            logger.info(f"Created dataset {self.dataset_id}")
    
    def create_table(self, table_name: str, force_recreate: bool = False) -> bool:
        """Create a single table with proper configuration."""
        config = BigQueryTableConfig.get_table_configs().get(table_name)
        if not config:
            raise ValueError(f"Unknown table: {table_name}")
        
        table_ref = self.dataset_ref.table(table_name)
        
        try:
            # Check if table exists
            existing_table = self.client.get_table(table_ref)
            if force_recreate:
                self.client.delete_table(table_ref)
                logger.info(f"Deleted existing table {table_name}")
            else:
                logger.info(f"Table {table_name} already exists")
                return False
                
        except NotFound:
            pass  # Table doesn't exist, proceed with creation
        
        # Create table configuration
        table = bigquery.Table(table_ref, schema=config["schema"])
        table.description = config["description"]
        
        # Configure partitioning
        if config.get("partition_field"):
            if config["partition_type"] == bigquery.TimePartitioningType.DAY:
                table.time_partitioning = bigquery.TimePartitioning(
                    type_=config["partition_type"],
                    field=config["partition_field"]
                )
                table.require_partition_filter = True
        
        # Configure clustering
        if config.get("clustering_fields"):
            table.clustering_fields = config["clustering_fields"]
        
        # Create the table
        table = self.client.create_table(table, timeout=30)
        logger.info(f"Created table {table_name} with {len(config['schema'])} fields")
        return True
    
    def create_all_tables(self, force_recreate: bool = False) -> Dict[str, bool]:
        """Create all ChainWeave tables."""
        results = {}
        table_configs = BigQueryTableConfig.get_table_configs()
        
        # Create tables in dependency order
        creation_order = [
            "nft_collections",
            "nft_metadata", 
            "transactions",
            "wallet_profiles",
            "whale_alerts",
            "market_analytics"
        ]
        
        for table_name in creation_order:
            try:
                results[table_name] = self.create_table(table_name, force_recreate)
            except Exception as e:
                logger.error(f"Failed to create table {table_name}: {e}")
                results[table_name] = False
        
        return results
    
    def update_table_schema(self, table_name: str, new_schema: List[bigquery.SchemaField]) -> bool:
        """Update table schema (additive changes only)."""
        table_ref = self.dataset_ref.table(table_name)
        
        try:
            table = self.client.get_table(table_ref)
            
            # BigQuery only supports additive schema changes
            table.schema = new_schema
            table = self.client.update_table(table, ["schema"])
            
            logger.info(f"Updated schema for table {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update schema for {table_name}: {e}")
            return False
    
    def validate_schema_compatibility(self, table_name: str, new_schema: List[bigquery.SchemaField]) -> List[str]:
        """Validate that new schema is compatible with existing data."""
        issues = []
        
        try:
            table_ref = self.dataset_ref.table(table_name)
            existing_table = self.client.get_table(table_ref)
            existing_schema = existing_table.schema
            
            # Create lookup for existing fields
            existing_fields = {field.name: field for field in existing_schema}
            
            for new_field in new_schema:
                if new_field.name in existing_fields:
                    existing_field = existing_fields[new_field.name]
                    
                    # Check for incompatible changes
                    if new_field.field_type != existing_field.field_type:
                        issues.append(f"Field {new_field.name}: type change from {existing_field.field_type} to {new_field.field_type}")
                    
                    if new_field.mode == "REQUIRED" and existing_field.mode != "REQUIRED":
                        issues.append(f"Field {new_field.name}: cannot change from optional to required")
        
        except NotFound:
            # Table doesn't exist, no compatibility issues
            pass
        except Exception as e:
            issues.append(f"Error validating schema: {e}")
        
        return issues
    
    def create_analytics_views(self) -> Dict[str, bool]:
        """Create analytical views for common queries."""
        results = {}
        
        for view_name, view_sql in ANALYTICS_VIEWS.items():
            try:
                formatted_sql = view_sql.format(
                    project_id=self.project_id,
                    dataset_id=self.dataset_id
                )
                
                query_job = self.client.query(formatted_sql)
                query_job.result()  # Wait for completion
                
                results[view_name] = True
                logger.info(f"Created view {view_name}")
                
            except Exception as e:
                logger.error(f"Failed to create view {view_name}: {e}")
                results[view_name] = False
        
        return results
    
    def backup_table(self, table_name: str, backup_suffix: Optional[str] = None) -> str:
        """Create a backup copy of a table before migration."""
        if not backup_suffix:
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        backup_table_name = f"{table_name}_backup_{backup_suffix}"
        
        # Create backup table by copying data
        source_table_ref = self.dataset_ref.table(table_name)
        backup_table_ref = self.dataset_ref.table(backup_table_name)
        
        copy_job = self.client.copy_table(source_table_ref, backup_table_ref)
        copy_job.result()  # Wait for completion
        
        logger.info(f"Created backup table {backup_table_name}")
        return backup_table_name
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get detailed information about a table."""
        try:
            table_ref = self.dataset_ref.table(table_name)
            table = self.client.get_table(table_ref)
            
            return {
                "name": table.table_id,
                "created": table.created.isoformat() if table.created else None,
                "modified": table.modified.isoformat() if table.modified else None,
                "num_rows": table.num_rows,
                "num_bytes": table.num_bytes,
                "schema_fields": len(table.schema),
                "partition_type": table.time_partitioning.type_.name if table.time_partitioning else None,
                "clustering_fields": table.clustering_fields,
                "description": table.description
            }
        except NotFound:
            return {"error": "Table not found"}
        except Exception as e:
            return {"error": str(e)}
    
    def validate_data_integrity(self, table_name: str) -> Dict[str, Any]:
        """Run basic data integrity checks on a table."""
        results = {
            "table_name": table_name,
            "checks": {},
            "issues": [],
            "total_rows": 0
        }
        
        try:
            # Get row count
            query = f"SELECT COUNT(*) as total FROM `{self.project_id}.{self.dataset_id}.{table_name}`"
            query_job = self.client.query(query)
            row = list(query_job)[0]
            results["total_rows"] = row.total
            
            # Table-specific validation
            if table_name == "transactions":
                # Check for orphaned transactions (no collection_id)
                query = f"""
                SELECT COUNT(*) as orphaned_transactions
                FROM `{self.project_id}.{self.dataset_id}.transactions` t
                LEFT JOIN `{self.project_id}.{self.dataset_id}.nft_collections` c
                ON t.collection_id = c.collection_id
                WHERE t.collection_id IS NOT NULL AND c.collection_id IS NULL
                """
                query_job = self.client.query(query)
                row = list(query_job)[0]
                if row.orphaned_transactions > 0:
                    results["issues"].append(f"{row.orphaned_transactions} transactions reference missing collections")
            
            elif table_name == "nft_metadata":
                # Check for NFTs without collections
                query = f"""
                SELECT COUNT(*) as orphaned_nfts
                FROM `{self.project_id}.{self.dataset_id}.nft_metadata` n
                LEFT JOIN `{self.project_id}.{self.dataset_id}.nft_collections` c
                ON n.collection_id = c.collection_id
                WHERE c.collection_id IS NULL
                """
                query_job = self.client.query(query)
                row = list(query_job)[0]
                if row.orphaned_nfts > 0:
                    results["issues"].append(f"{row.orphaned_nfts} NFTs reference missing collections")
            
            results["status"] = "healthy" if not results["issues"] else "issues_found"
            
        except Exception as e:
            results["error"] = str(e)
            results["status"] = "error"
        
        return results


class MigrationScript:
    """Base class for migration scripts."""
    
    def __init__(self, migration_manager: BigQueryMigrationManager):
        self.mgr = migration_manager
        self.name = self.__class__.__name__
    
    def up(self) -> bool:
        """Apply the migration."""
        raise NotImplementedError
    
    def down(self) -> bool:
        """Rollback the migration."""
        raise NotImplementedError
    
    def validate(self) -> List[str]:
        """Validate migration prerequisites."""
        return []


class InitialSchemaMigration(MigrationScript):
    """Initial schema creation migration."""
    
    def up(self) -> bool:
        """Create all initial tables."""
        logger.info("Running initial schema migration")
        
        # Create all tables
        results = self.mgr.create_all_tables()
        
        # Create views
        view_results = self.mgr.create_analytics_views()
        
        # Check if all succeeded
        all_success = all(results.values()) and all(view_results.values())
        
        if all_success:
            logger.info("Initial schema migration completed successfully")
        else:
            logger.error("Initial schema migration had failures")
            logger.error(f"Table results: {results}")
            logger.error(f"View results: {view_results}")
        
        return all_success
    
    def down(self) -> bool:
        """Drop all tables (use with caution)."""
        logger.warning("Rolling back initial schema - this will drop all data!")
        
        table_names = list(BigQueryTableConfig.get_table_configs().keys())
        view_names = list(ANALYTICS_VIEWS.keys())
        
        success = True
        
        # Drop views first
        for view_name in view_names:
            try:
                view_ref = self.mgr.dataset_ref.table(view_name)
                self.mgr.client.delete_table(view_ref)
                logger.info(f"Dropped view {view_name}")
            except NotFound:
                pass  # Already doesn't exist
            except Exception as e:
                logger.error(f"Failed to drop view {view_name}: {e}")
                success = False
        
        # Drop tables in reverse order
        for table_name in reversed(table_names):
            try:
                table_ref = self.mgr.dataset_ref.table(table_name)
                self.mgr.client.delete_table(table_ref)
                logger.info(f"Dropped table {table_name}")
            except NotFound:
                pass  # Already doesn't exist
            except Exception as e:
                logger.error(f"Failed to drop table {table_name}: {e}")
                success = False
        
        return success


def run_migration(project_id: str, dataset_id: str, migration_class: type = InitialSchemaMigration) -> bool:
    """Run a specific migration."""
    try:
        mgr = BigQueryMigrationManager(project_id, dataset_id)
        migration = migration_class(mgr)
        
        # Validate prerequisites
        issues = migration.validate()
        if issues:
            logger.error(f"Migration validation failed: {issues}")
            return False
        
        # Run migration
        success = migration.up()
        
        if success:
            logger.info(f"Migration {migration.name} completed successfully")
        else:
            logger.error(f"Migration {migration.name} failed")
        
        return success
        
    except Exception as e:
        logger.error(f"Migration failed with exception: {e}")
        return False


def get_migration_status(project_id: str, dataset_id: str) -> Dict[str, Any]:
    """Get current migration status and table health."""
    mgr = BigQueryMigrationManager(project_id, dataset_id)
    
    status = {
        "dataset_exists": True,
        "tables": {},
        "views": {},
        "last_checked": datetime.now().isoformat()
    }
    
    # Check tables
    table_names = list(BigQueryTableConfig.get_table_configs().keys())
    for table_name in table_names:
        info = mgr.get_table_info(table_name)
        integrity = mgr.validate_data_integrity(table_name) if "error" not in info else None
        
        status["tables"][table_name] = {
            "exists": "error" not in info,
            "info": info,
            "integrity": integrity
        }
    
    # Check views
    for view_name in ANALYTICS_VIEWS.keys():
        try:
            view_ref = mgr.dataset_ref.table(view_name)
            mgr.client.get_table(view_ref)
            status["views"][view_name] = {"exists": True}
        except NotFound:
            status["views"][view_name] = {"exists": False}
        except Exception as e:
            status["views"][view_name] = {"exists": False, "error": str(e)}
    
    return status