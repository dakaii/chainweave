"""Bridge service to connect webhook receiver to data processor locally."""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any

from local_processor import LocalDataProcessor

logger = logging.getLogger(__name__)


class WebhookBridge:
    """Bridge between webhook service and data processor for local development."""

    def __init__(self, webhook_url: str = "http://localhost:8000", processor_db: str = "local_chainweave.db"):
        """Initialize the webhook bridge."""
        self.webhook_url = webhook_url
        self.processor = LocalDataProcessor(processor_db)
        self.session = None

    async def start(self):
        """Start the bridge service."""

        self.session = aiohttp.ClientSession()
        logger.info(f"Webhook bridge started, monitoring {self.webhook_url}")

        # In a real implementation, this would:
        # 1. Subscribe to Pub/Sub messages
        # 2. Or poll a message queue
        # 3. Or receive webhooks directly

        # For demo, we'll simulate receiving webhook data
        await self._simulate_webhook_processing()

    async def _simulate_webhook_processing(self):
        """Simulate processing webhook data."""

        print("🌉 Webhook Bridge: Simulating webhook data processing...")
        print("This would normally receive data from Pub/Sub or direct webhooks")

        # Import test data generator
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent.parent / "tests"))

        from test_local_processor import generate_mock_webhook_payload

        # Process simulated webhook data
        for i in range(10):
            payload = generate_mock_webhook_payload()

            print(f"📨 Processing webhook #{i+1}")
            success = await self.processor.process_webhook_payload(payload)

            if success:
                price_sol = payload["events"]["nft"]["amount"] / 1_000_000_000
                print(f"✅ Successfully processed {price_sol:.2f} SOL transaction")
            else:
                print("❌ Failed to process webhook")

            await asyncio.sleep(2)

        # Show final stats
        stats = self.processor.get_stats()
        print(f"\n📊 Processing complete: {stats}")

    async def process_webhook_data(self, webhook_data: Dict[str, Any]) -> bool:
        """Process incoming webhook data."""

        try:
            success = await self.processor.process_webhook_payload(webhook_data)

            if success:
                logger.info("Webhook data processed successfully")
            else:
                logger.warning("Failed to process webhook data")

            return success

        except Exception as e:
            logger.error(f"Exception processing webhook data: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""

        try:
            stats = self.processor.get_stats()
            return {
                "status": "healthy",
                "bridge_active": True,
                "processor_stats": stats,
                "timestamp": asyncio.get_event_loop().time()
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }

    async def stop(self):
        """Stop the bridge service."""

        if self.session:
            await self.session.close()

        logger.info("Webhook bridge stopped")


async def main():
    """Main entry point for webhook bridge."""

    logging.basicConfig(level=logging.INFO)

    bridge = WebhookBridge()

    try:
        await bridge.start()
    except KeyboardInterrupt:
        print("\n🛑 Webhook bridge stopped by user")
    except Exception as e:
        print(f"❌ Webhook bridge failed: {e}")
    finally:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())