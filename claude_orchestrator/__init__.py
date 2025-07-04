"""
Claude Orchestrator - Opus Manager with Sonnet Workers
"""

__version__ = "0.1.0"

from .main import main

# Auto-enable Enhanced UI if configured
import json
import os
from pathlib import Path

def _check_and_enable_enhanced_ui():
    """Check config and enable Enhanced UI if configured"""
    try:
        # Check for orchestrator_config.json in current directory or parent
        for config_path in [Path("orchestrator_config.json"), Path("../orchestrator_config.json")]:
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                
                # Check if enhanced UI is enabled
                ui_mode = config.get("monitoring", {}).get("ui_mode", "")
                if ui_mode == "enhanced":
                    # Import the UI patch to enable enhanced display
                    try:
                        from . import ui_patch
                        return True
                    except ImportError:
                        pass
                break
    except:
        pass
    return False

# Check and enable on module import
_ui_enabled = _check_and_enable_enhanced_ui()

__all__ = ["main"]