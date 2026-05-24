import logging
import os

def setup_logging(filename="app.log"):
    """Setup logging configuration and return logger"""
    # Create logs directory if it doesn't exist
    os.makedirs(".logs", exist_ok=True)
    
    # Configure logging to write to file only
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f".logs/{filename}")
        ]
    )
    
    # Suppress noisy third-party loggers
    logging.getLogger('mcp').setLevel(logging.ERROR)
    logging.getLogger('httpx').setLevel(logging.ERROR)
    logging.getLogger('openai').setLevel(logging.ERROR)

    return logging.getLogger('dashboard')