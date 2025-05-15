from typing import Dict, Any, Optional
import os
import tomli  # For reading TOML files


class ConfigManager:
    """
    Singleton configuration manager that loads and provides access to configuration.
    
    Loads configuration from TOML files and provides a centralized access point
    for all application configuration.
    """
    _instance = None
    _config = None

    @classmethod
    def get_config(cls, config_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the configuration, loading it if necessary. Creates the singleton instance
        if it doesn't exist yet.
        
        Args:
            config_file (Optional[str]): Path to configuration file
            
        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        # Return cached config if available
        if cls._config is not None:
            return cls._config
            
        # Create singleton instance if needed 
        if cls._instance is None:
            cls._instance = cls()
            
        # Load the configuration
        config = {}
        
        # Default config file paths to try
        config_paths = [
            config_file,  # User-specified path
            "config.toml",  # Current directory
            os.path.join(os.path.dirname(__file__), "config.toml"),  # Module directory
            os.path.expanduser("~/.config/edgar_parser/config.toml")  # User config directory
        ]
        
        # Try to load from config files
        for path in config_paths:
            if path and os.path.isfile(path):
                try:
                    with open(path, "rb") as f:
                        config = tomli.load(f)
                    print(f"Loaded configuration from {path}")
                    break
                except Exception as e:
                    print(f"Error loading config from {path}: {e}")
                    # Continue to next config path on error
                    pass
       
        cls._config = config
        return config