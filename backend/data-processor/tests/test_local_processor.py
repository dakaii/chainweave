"""Test script for local data processor with mock data."""

import asyncio
import json
import logging
import random
import string
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent))

from src.local_processor import LocalDataProcessor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_mock_webhook_payload() -> dict:
    """Generate a mock Helius webhook payload."""

    collections = [
        "mad-lads-collection",
        "okay-bears-collection",
        "solana-monkey-business",
        "degenerate-apes-collection",
        "thugbirdz-collection"
    ]

    wallets = [
        "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "J1S9H3QjnRtBbbuD4HjPV6RpRhwuk4zKbxsnCHuTgh9w",
        "8qbHbw2BbbTHBW1sbeqakYXVKRQM8Ne7pLK7m6CVfeR5",
        "DhVB8wAVRX11e6xKb7uJyVdejjRNbBRoKDSz2qQWcAGF",
        "2BjWRjjYAk6txcfQQj1zKF1VTGXr9Vq7QWaFKfgPYc5B"
    ]

    marketplaces = ["magic-eden", "solanart", "opensea", "tensor"]

    # Generate transaction signature
    signature = ''.join(random.choices(string.ascii_letters + string.digits, k=88))

    # Generate mint address
    mint_address = ''.join(random.choices(string.ascii_letters + string.digits, k=44))

    # Random price (some high values for whale testing)
    price_lamports = random.choice([
        random.randint(100_000_000, 50_000_000_000),  # 0.1 - 50 SOL (normal)
        random.randint(100_000_000_000, 1_000_000_000_000),  # 100 - 1000 SOL (whale)
    ])

    return {
        "type": "ENHANCED",
        "signature": signature,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "slot": random.randint(100000000, 200000000),
        "events": {
            "nft": {
                "type": "sale",
                "nftMint": mint_address,
                "collection": random.choice(collections),
                "seller": random.choice(wallets),
                "buyer": random.choice(wallets),
                "amount": price_lamports,
                "marketplace": random.choice(marketplaces)
            }
        }
    }


async def test_processor():
    """Test the local data processor."""

    print("🧪 Testing ChainWeave Local Data Processor")
    print("=" * 50)

    # Initialize processor
    processor = LocalDataProcessor("test_chainweave.db")

    # Generate and process mock transactions
    num_transactions = 20
    print(f"📦 Processing {num_transactions} mock transactions...")

    for i in range(num_transactions):
        payload = generate_mock_webhook_payload()
        success = await processor.process_webhook_payload(payload)

        if success:
            price_sol = payload["events"]["nft"]["amount"] / 1_000_000_000
            print(f"✅ Transaction {i+1}: {price_sol:.2f} SOL")
        else:
            print(f"❌ Transaction {i+1}: Failed")

        # Small delay to simulate real processing
        await asyncio.sleep(0.1)

    # Show statistics
    print("\n📊 Processing Statistics:")
    print("-" * 30)
    stats = processor.get_stats()
    for key, value in stats.items():
        print(f"{key.title()}: {value}")

    print("\n🎉 Test completed successfully!")


async def demo_real_time_processing():
    """Demo continuous processing simulation."""

    print("\n🔄 Starting real-time processing simulation...")
    print("Press Ctrl+C to stop")

    processor = LocalDataProcessor("demo_chainweave.db")

    try:
        while True:
            payload = generate_mock_webhook_payload()
            await processor.process_webhook_payload(payload)

            price_sol = payload["events"]["nft"]["amount"] / 1_000_000_000
            collection = payload["events"]["nft"]["collection"]

            print(f"🔗 Processed: {price_sol:.2f} SOL | {collection}")

            # Random delay between 1-5 seconds
            await asyncio.sleep(random.uniform(1, 5))

    except KeyboardInterrupt:
        print("\n⏹️  Real-time simulation stopped")
        stats = processor.get_stats()
        print(f"📊 Final stats: {stats}")


async def main():
    """Main test function."""

    import argparse

    parser = argparse.ArgumentParser(description='Test ChainWeave Data Processor')
    parser.add_argument('--mode', choices=['test', 'demo'], default='test',
                       help='Run mode: test (batch) or demo (real-time)')

    args = parser.parse_args()

    if args.mode == 'test':
        await test_processor()
    elif args.mode == 'demo':
        await demo_real_time_processing()


if __name__ == "__main__":
    asyncio.run(main())