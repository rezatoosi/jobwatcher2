# src/ai/test_ai.py
"""Minimal AI provider test."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config.loader import load_config
from src.ai.manager import AIProviderManager


def test_ai_basic():
    """Send a minimal prompt and verify response."""

    load_dotenv()

    config_path = project_root / "config.yaml"
    config = load_config(config_path)
    
    if not config.ai_providers or not config.ai_providers.enabled:
        print("AI is disabled in config")
        return
    
    manager = AIProviderManager(config.ai_providers, config.network)
    
    if not manager.enabled:
        print("No enabled providers found")
        return
    
    print(f"Active providers: {manager.list_providers()}")
    
    response = manager.send_request(
        user_prompt="Say hello in one word",
        temperature=0.5,
        max_tokens=10,
    )
    
    print(f"\nProvider: {response.provider}")
    print(f"Model: {response.model}")
    print(f"Success: {response.success}")
    print(f"Response: {response.content}")
    
    if response.error:
        print(f"Error: {response.error}")


if __name__ == "__main__":
    test_ai_basic()
