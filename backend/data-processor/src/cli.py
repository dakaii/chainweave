"""CLI interface for the data processor service."""

import asyncio
import argparse
import logging
from pathlib import Path
import sys

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.main import DataProcessor


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('data-processor.log')
        ]
    )


async def run_processor():
    """Run the data processor."""

    processor = DataProcessor()
    await processor.start()


def main():
    """Main CLI entry point."""

    parser = argparse.ArgumentParser(description='ChainWeave Data Processor')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Set logging level')

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    print("🔗 ChainWeave Data Processor Starting...")
    print("Press Ctrl+C to stop")

    try:
        asyncio.run(run_processor())
    except KeyboardInterrupt:
        print("\n👋 Data Processor stopped by user")
    except Exception as e:
        print(f"❌ Data Processor failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()