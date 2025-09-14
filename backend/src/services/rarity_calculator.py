"""Rarity calculation service for ChainWeave.

Advanced rarity scoring and ranking system:
- Statistical rarity analysis
- Trait frequency calculation
- Market-based rarity weighting
- Rarity tier classification
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from google.cloud import bigquery
import json
import math
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class RarityCalculator:
    """Calculates rarity scores and ranks for NFT collections."""
    
    def __init__(self, project_id: str, dataset_id: str):
        """Initialize rarity calculator."""
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.client = bigquery.Client(project=project_id)
    
    async def calculate_collection_rarity(
        self, 
        collection_id: str, 
        nfts: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate rarity scores for all NFTs in a collection."""
        
        logger.info(f"Calculating rarity for {len(nfts)} NFTs in collection {collection_id}")
        
        try:
            # Extract all attributes and calculate frequencies
            trait_frequencies = self._calculate_trait_frequencies(nfts)
            
            # Calculate individual rarity scores
            rarity_scores = {}
            
            for nft in nfts:
                mint_address = nft['mint_address']
                attributes = nft.get('attributes', {})
                
                if isinstance(attributes, str):
                    try:
                        attributes = json.loads(attributes)
                    except json.JSONDecodeError:
                        attributes = {}
                
                # Calculate statistical rarity score
                statistical_score = self._calculate_statistical_rarity(
                    attributes, trait_frequencies, len(nfts)
                )
                
                # Get market-based weighting (if available)
                market_weight = await self._get_market_based_weighting(
                    collection_id, attributes
                )
                
                # Calculate composite rarity score
                composite_score = statistical_score * market_weight
                
                rarity_scores[mint_address] = {
                    'statistical_score': statistical_score,
                    'market_weight': market_weight,
                    'composite_score': composite_score,
                    'attributes': attributes
                }
            
            # Rank NFTs by rarity score (1 = rarest)
            sorted_nfts = sorted(
                rarity_scores.items(),
                key=lambda x: x[1]['composite_score'],
                reverse=True
            )
            
            # Assign ranks
            for rank, (mint_address, data) in enumerate(sorted_nfts, 1):
                rarity_scores[mint_address]['rank'] = rank
                rarity_scores[mint_address]['score'] = data['composite_score']
            
            logger.info(f"Calculated rarity for {len(rarity_scores)} NFTs")
            
            return rarity_scores
            
        except Exception as e:
            logger.error(f"Failed to calculate collection rarity: {e}")
            return {}
    
    def _calculate_trait_frequencies(self, nfts: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """Calculate frequency of each trait value across the collection."""
        
        trait_counts = defaultdict(Counter)
        total_nfts = len(nfts)
        
        # Count occurrences of each trait value
        for nft in nfts:
            attributes = nft.get('attributes', {})
            
            if isinstance(attributes, str):
                try:
                    attributes = json.loads(attributes)
                except json.JSONDecodeError:
                    continue
            
            for trait_type, trait_value in attributes.items():
                if trait_value is not None:  # Handle null values
                    trait_counts[trait_type][str(trait_value)] += 1
        
        # Convert counts to frequencies
        trait_frequencies = {}
        for trait_type, value_counts in trait_counts.items():
            trait_frequencies[trait_type] = {}
            for trait_value, count in value_counts.items():
                trait_frequencies[trait_type][trait_value] = count / total_nfts
        
        return trait_frequencies
    
    def _calculate_statistical_rarity(
        self, 
        attributes: Dict[str, Any], 
        trait_frequencies: Dict[str, Dict[str, float]], 
        total_nfts: int
    ) -> float:
        """Calculate statistical rarity score using multiple methods."""
        
        if not attributes:
            return 0.0
        
        # Method 1: Trait Rarity (1/frequency sum)
        trait_rarity_score = 0.0
        valid_traits = 0
        
        for trait_type, trait_value in attributes.items():
            trait_value_str = str(trait_value)
            
            if trait_type in trait_frequencies and trait_value_str in trait_frequencies[trait_type]:
                frequency = trait_frequencies[trait_type][trait_value_str]
                if frequency > 0:
                    trait_rarity_score += 1.0 / frequency
                    valid_traits += 1
        
        if valid_traits == 0:
            return 0.0
        
        # Method 2: Information Content (sum of -log2(frequency))
        information_content = 0.0
        for trait_type, trait_value in attributes.items():
            trait_value_str = str(trait_value)
            
            if trait_type in trait_frequencies and trait_value_str in trait_frequencies[trait_type]:
                frequency = trait_frequencies[trait_type][trait_value_str]
                if frequency > 0:
                    information_content += -math.log2(frequency)
        
        # Method 3: Jaccard Distance (uniqueness in trait combinations)
        # This would require comparing against all other NFTs - simplified for now
        combination_rarity = len(attributes) * 10  # Simple approximation
        
        # Combine methods with weights
        statistical_score = (
            trait_rarity_score * 0.4 +
            information_content * 0.4 +
            combination_rarity * 0.2
        )
        
        return statistical_score
    
    async def _get_market_based_weighting(
        self, 
        collection_id: str, 
        attributes: Dict[str, Any]
    ) -> float:
        """Calculate market-based weighting for traits."""
        
        # This would analyze historical sales data to weight traits by their market performance
        # For now, return neutral weighting
        return 1.0
        
        # Future implementation would include:
        # - Average sale price for NFTs with specific traits
        # - Trading velocity for different trait combinations
        # - Listing/sale ratios by trait
        # - Price trend analysis
    
    async def get_collection_nfts(self, collection_id: str) -> List[Dict[str, Any]]:
        """Get all NFTs in a collection for rarity calculation."""
        
        query = f"""
        SELECT 
            mint_address,
            name,
            attributes,
            current_owner,
            rarity_rank,
            rarity_score
        FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
        WHERE collection_id = @collection_id
          AND partition_date = (
              SELECT MAX(partition_date) 
              FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
              WHERE collection_id = @collection_id
          )
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        
        nfts = []
        for row in query_job:
            nfts.append({
                'mint_address': row.mint_address,
                'name': row.name,
                'attributes': row.attributes,
                'current_owner': row.current_owner,
                'existing_rank': row.rarity_rank,
                'existing_score': row.rarity_score
            })
        
        return nfts
    
    async def update_nft_rarity(
        self, 
        mint_address: str, 
        rarity_rank: int, 
        rarity_score: float
    ) -> bool:
        """Update rarity information for a specific NFT."""
        
        try:
            # Update the most recent partition
            update_query = f"""
            UPDATE `{self.project_id}.{self.dataset_id}.nft_metadata`
            SET 
                rarity_rank = @rarity_rank,
                rarity_score = @rarity_score
            WHERE mint_address = @mint_address
              AND partition_date = CURRENT_DATE()
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("mint_address", "STRING", mint_address),
                    bigquery.ScalarQueryParameter("rarity_rank", "INT64", rarity_rank),
                    bigquery.ScalarQueryParameter("rarity_score", "FLOAT64", rarity_score)
                ]
            )
            
            query_job = self.client.query(update_query, job_config=job_config)
            query_job.result()  # Wait for completion
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update rarity for {mint_address}: {e}")
            return False
    
    async def calculate_rarity_stats(self, collection_id: str) -> Dict[str, Any]:
        """Calculate collection-level rarity statistics."""
        
        try:
            # Get trait distribution
            query = f"""
            WITH trait_analysis AS (
                SELECT 
                    mint_address,
                    attributes,
                    rarity_rank,
                    rarity_score
                FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
                WHERE collection_id = @collection_id
                  AND partition_date = CURRENT_DATE()
            )
            SELECT 
                COUNT(*) as total_nfts,
                AVG(rarity_score) as avg_score,
                STDDEV(rarity_score) as score_stddev,
                MIN(rarity_score) as min_score,
                MAX(rarity_score) as max_score,
                APPROX_PERCENTILES(rarity_score, 10) as score_percentiles
            FROM trait_analysis
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job)
            
            if not results:
                return {}
            
            row = results[0]
            
            # Calculate tier distribution
            tier_distribution = await self._calculate_tier_distribution(collection_id)
            
            # Count unique traits
            unique_traits_count = await self._count_unique_traits(collection_id)
            
            return {
                'total_nfts': row.total_nfts,
                'avg_score': float(row.avg_score) if row.avg_score else 0.0,
                'score_stddev': float(row.score_stddev) if row.score_stddev else 0.0,
                'min_score': float(row.min_score) if row.min_score else 0.0,
                'max_score': float(row.max_score) if row.max_score else 0.0,
                'unique_traits': unique_traits_count,
                'tier_distribution': tier_distribution
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate rarity stats: {e}")
            return {}
    
    async def _calculate_tier_distribution(self, collection_id: str) -> Dict[str, int]:
        """Calculate how many NFTs fall into each rarity tier."""
        
        query = f"""
        WITH rarity_tiers AS (
            SELECT 
                mint_address,
                rarity_rank,
                CASE 
                    WHEN rarity_rank <= 10 THEN 'Mythic'
                    WHEN rarity_rank <= 100 THEN 'Legendary'
                    WHEN rarity_rank <= 500 THEN 'Epic'
                    WHEN rarity_rank <= 2000 THEN 'Rare'
                    ELSE 'Common'
                END as tier
            FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
            WHERE collection_id = @collection_id
              AND partition_date = CURRENT_DATE()
        )
        SELECT 
            tier,
            COUNT(*) as count
        FROM rarity_tiers
        GROUP BY tier
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        
        distribution = {}
        for row in query_job:
            distribution[row.tier] = row.count
        
        return distribution
    
    async def _count_unique_traits(self, collection_id: str) -> int:
        """Count total number of unique trait types in collection."""
        
        query = f"""
        WITH trait_extraction AS (
            SELECT 
                JSON_EXTRACT_SCALAR(attributes, '$') as attr_json
            FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
            WHERE collection_id = @collection_id
              AND partition_date = CURRENT_DATE()
              AND attributes IS NOT NULL
        )
        SELECT COUNT(DISTINCT trait_key) as unique_traits
        FROM trait_extraction,
        UNNEST(JSON_EXTRACT_ARRAY(attr_json)) as trait_key
        """
        
        try:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job)
            
            return results[0].unique_traits if results else 0
            
        except Exception as e:
            logger.warning(f"Failed to count unique traits, using fallback: {e}")
            # Fallback: estimate from sample
            return await self._estimate_unique_traits_fallback(collection_id)
    
    async def _estimate_unique_traits_fallback(self, collection_id: str) -> int:
        """Fallback method to estimate unique traits."""
        
        query = f"""
        SELECT attributes
        FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
        WHERE collection_id = @collection_id
          AND partition_date = CURRENT_DATE()
          AND attributes IS NOT NULL
        LIMIT 100
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        
        all_trait_types = set()
        
        for row in query_job:
            try:
                if isinstance(row.attributes, str):
                    attributes = json.loads(row.attributes)
                else:
                    attributes = row.attributes or {}
                
                all_trait_types.update(attributes.keys())
                
            except (json.JSONDecodeError, TypeError):
                continue
        
        return len(all_trait_types)
    
    async def get_last_rarity_update(self, collection_id: str) -> Optional[datetime]:
        """Get timestamp of last rarity calculation for collection."""
        
        query = f"""
        SELECT MAX(ingested_at) as last_update
        FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
        WHERE collection_id = @collection_id
          AND rarity_rank IS NOT NULL
          AND rarity_score IS NOT NULL
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        results = list(query_job)
        
        if results and results[0].last_update:
            return results[0].last_update
        
        return None
    
    async def get_trait_rarity_analysis(
        self, collection_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """Get detailed trait rarity analysis for a collection."""
        
        # This would provide detailed analysis of each trait type and value
        # Including market performance correlation
        
        query = f"""
        WITH trait_analysis AS (
            SELECT 
                attributes,
                rarity_rank,
                last_sale_price
            FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
            WHERE collection_id = @collection_id
              AND partition_date = CURRENT_DATE()
              AND attributes IS NOT NULL
        )
        SELECT 
            COUNT(*) as total_nfts,
            AVG(last_sale_price) as avg_sale_price
        FROM trait_analysis
        """
        
        # This is a simplified implementation
        # Full implementation would parse JSON attributes and analyze each trait
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        results = list(query_job)
        
        if results:
            return {
                'collection_overview': {
                    'total_nfts': results[0].total_nfts,
                    'avg_sale_price': float(results[0].avg_sale_price) if results[0].avg_sale_price else 0.0
                }
            }
        
        return {}