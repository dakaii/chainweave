"""Local development version of data processor using SQLite."""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class LocalDataProcessor:
    """Local development data processor using SQLite."""

    def __init__(self, db_path: str = "chainweave_local.db"):
        """Initialize the local processor."""
        self.db_path = db_path
        self.setup_database()

    def setup_database(self):
        """Setup SQLite database with required tables."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_signature TEXT PRIMARY KEY,
                mint_address TEXT NOT NULL,
                collection_id TEXT,
                event_type TEXT NOT NULL,
                from_address TEXT,
                to_address TEXT,
                price_sol REAL NOT NULL,
                timestamp TEXT NOT NULL,
                slot INTEGER,
                marketplace TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Create collections table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                collection_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                total_supply INTEGER,
                floor_price REAL,
                total_volume REAL,
                holder_count INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create whale_alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whale_alerts (
                alert_id TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                collection_id TEXT,
                amount_sol REAL NOT NULL,
                severity TEXT NOT NULL,
                triggered_at TEXT NOT NULL,
                details TEXT
            )
        """)

        # Create wallet_profiles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallet_profiles (
                wallet_address TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                total_transactions INTEGER DEFAULT 0,
                total_volume_traded REAL DEFAULT 0.0,
                whale_status TEXT DEFAULT 'regular',
                trading_behavior TEXT DEFAULT 'unknown'
            )
        """)

        conn.commit()
        conn.close()

        logger.info(f"SQLite database initialized at {self.db_path}")

    async def process_webhook_payload(self, payload: Dict[str, Any]) -> bool:
        """Process a webhook payload locally."""

        try:
            # Extract transaction data
            transaction_data = self._extract_transaction_data(payload)
            if not transaction_data:
                return True

            # Store transaction
            await self._store_transaction(transaction_data)

            # Update wallet profiles
            await self._update_wallet_profiles(transaction_data)

            # Check for whale alerts
            whale_alert = await self._check_whale_activity(transaction_data)
            if whale_alert:
                await self._store_whale_alert(whale_alert)

            # Update collection metrics
            await self._update_collection_metrics(transaction_data)

            logger.info(f"Processed transaction: {transaction_data['transaction_signature']}")
            return True

        except Exception as e:
            logger.error(f"Failed to process payload: {e}")
            return False

    def _extract_transaction_data(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from payload."""

        try:
            if not all(key in payload for key in ['signature', 'timestamp', 'events']):
                return None

            events = payload.get('events', {})
            nft_event = events.get('nft', {})

            if not nft_event:
                return None

            return {
                'transaction_signature': payload['signature'],
                'mint_address': nft_event.get('nftMint'),
                'collection_id': nft_event.get('collection', 'unknown'),
                'event_type': nft_event.get('type', 'unknown'),
                'from_address': nft_event.get('seller'),
                'to_address': nft_event.get('buyer'),
                'price_sol': float(nft_event.get('amount', 0)) / 1_000_000_000,
                'timestamp': payload['timestamp'],
                'slot': payload.get('slot'),
                'marketplace': nft_event.get('marketplace')
            }

        except Exception as e:
            logger.error(f"Failed to extract transaction data: {e}")
            return None

    async def _store_transaction(self, transaction_data: Dict[str, Any]):
        """Store transaction in SQLite."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO transactions (
                    transaction_signature, mint_address, collection_id, event_type,
                    from_address, to_address, price_sol, timestamp, slot, marketplace, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction_data['transaction_signature'],
                transaction_data['mint_address'],
                transaction_data['collection_id'],
                transaction_data['event_type'],
                transaction_data['from_address'],
                transaction_data['to_address'],
                transaction_data['price_sol'],
                transaction_data['timestamp'],
                transaction_data['slot'],
                transaction_data['marketplace'],
                datetime.now(timezone.utc).isoformat()
            ))

            conn.commit()

        except Exception as e:
            logger.error(f"Failed to store transaction: {e}")
        finally:
            conn.close()

    async def _update_wallet_profiles(self, transaction_data: Dict[str, Any]):
        """Update wallet profiles."""

        addresses = [transaction_data.get('from_address'), transaction_data.get('to_address')]

        for address in addresses:
            if not address:
                continue

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                # Get existing profile
                cursor.execute("SELECT * FROM wallet_profiles WHERE wallet_address = ?", (address,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing
                    cursor.execute("""
                        UPDATE wallet_profiles SET
                            last_activity = ?,
                            total_transactions = total_transactions + 1,
                            total_volume_traded = total_volume_traded + ?
                        WHERE wallet_address = ?
                    """, (
                        transaction_data['timestamp'],
                        transaction_data['price_sol'],
                        address
                    ))
                else:
                    # Create new
                    cursor.execute("""
                        INSERT INTO wallet_profiles (
                            wallet_address, first_seen, last_activity, total_transactions, total_volume_traded
                        ) VALUES (?, ?, ?, 1, ?)
                    """, (
                        address,
                        transaction_data['timestamp'],
                        transaction_data['timestamp'],
                        transaction_data['price_sol']
                    ))

                conn.commit()

            except Exception as e:
                logger.error(f"Failed to update wallet profile: {e}")
            finally:
                conn.close()

    async def _check_whale_activity(self, transaction_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for whale activity."""

        price_sol = transaction_data.get('price_sol', 0.0)
        wallet_address = transaction_data.get('to_address') or transaction_data.get('from_address')

        # Simple whale threshold
        if price_sol >= 100.0 and wallet_address:
            return {
                'alert_id': f"alert_{int(datetime.now().timestamp())}",
                'wallet_address': wallet_address,
                'alert_type': 'large_purchase',
                'collection_id': transaction_data['collection_id'],
                'amount_sol': price_sol,
                'severity': 'high' if price_sol >= 500.0 else 'medium',
                'triggered_at': transaction_data['timestamp'],
                'details': json.dumps({
                    'transaction_signature': transaction_data['transaction_signature'],
                    'marketplace': transaction_data['marketplace']
                })
            }

        return None

    async def _store_whale_alert(self, whale_alert: Dict[str, Any]):
        """Store whale alert."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO whale_alerts (
                    alert_id, wallet_address, alert_type, collection_id,
                    amount_sol, severity, triggered_at, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                whale_alert['alert_id'],
                whale_alert['wallet_address'],
                whale_alert['alert_type'],
                whale_alert['collection_id'],
                whale_alert['amount_sol'],
                whale_alert['severity'],
                whale_alert['triggered_at'],
                whale_alert['details']
            ))

            conn.commit()
            logger.info(f"Whale alert stored: {whale_alert['alert_id']}")

        except Exception as e:
            logger.error(f"Failed to store whale alert: {e}")
        finally:
            conn.close()

    async def _update_collection_metrics(self, transaction_data: Dict[str, Any]):
        """Update collection metrics."""

        collection_id = transaction_data.get('collection_id')
        if not collection_id:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get existing collection
            cursor.execute("SELECT * FROM collections WHERE collection_id = ?", (collection_id,))
            existing = cursor.fetchone()

            if existing:
                # Update existing
                cursor.execute("""
                    UPDATE collections SET
                        total_volume = total_volume + ?,
                        updated_at = ?
                    WHERE collection_id = ?
                """, (
                    transaction_data['price_sol'],
                    datetime.now(timezone.utc).isoformat(),
                    collection_id
                ))
            else:
                # Create new
                cursor.execute("""
                    INSERT INTO collections (
                        collection_id, name, total_supply, floor_price, total_volume, holder_count, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    collection_id,
                    f"Collection {collection_id[:8]}",
                    10000,
                    transaction_data['price_sol'],
                    transaction_data['price_sol'],
                    1,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat()
                ))

            conn.commit()

        except Exception as e:
            logger.error(f"Failed to update collection metrics: {e}")
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get transaction count
            cursor.execute("SELECT COUNT(*) FROM transactions")
            transaction_count = cursor.fetchone()[0]

            # Get whale alerts count
            cursor.execute("SELECT COUNT(*) FROM whale_alerts")
            whale_alerts_count = cursor.fetchone()[0]

            # Get collection count
            cursor.execute("SELECT COUNT(*) FROM collections")
            collection_count = cursor.fetchone()[0]

            # Get wallet count
            cursor.execute("SELECT COUNT(*) FROM wallet_profiles")
            wallet_count = cursor.fetchone()[0]

            return {
                'transactions': transaction_count,
                'whale_alerts': whale_alerts_count,
                'collections': collection_count,
                'wallets': wallet_count,
                'database': self.db_path
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
        finally:
            conn.close()