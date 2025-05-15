"""
App Utilities Package

Provides centralized configuration and logging management for Python applications.
"""

from app_utils.config_manager import ConfigManager
from app_utils.logger_manager import LoggingManager

__version__ = "1.0.0"
__author__ = "Horia & Matilda"

# Export main components for easy imports
__all__ = ['ConfigManager', 'LoggingManager']
