from typing import Dict, Any, Optional
import logging


class LoggingManager:
    """
    Centralized logging configuration manager.
    
    Configures loggers for different components of the application based on
    configuration settings.
    """
    
    # Dictionary to keep track of configured loggers
    _configured_loggers = {}
    
    @staticmethod
    def get_logger(logger_name: str, config: Dict[str, Any], log_level: Optional[int] = None) -> logging.Logger:
        """
        Get a configured logger for a component.
        
        Args:
            logger_name (str): Name of the logger
            config (Dict[str, Any]): Configuration dictionary
            log_level (Optional[int]): Override logging level
            
        Returns:
            logging.Logger: Configured logger
        """
        # Check if logger was already configured
        if logger_name in LoggingManager._configured_loggers:
            return LoggingManager._configured_loggers[logger_name]
            
        log_config = config.get("Logging", {})
        
        # Determine log level
        if log_level is None:
            log_level_str = log_config.get("level", "INFO")
            log_level = getattr(logging, log_level_str) if isinstance(log_level_str, str) else log_level_str
        
        # Get or create logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level)
        
        # Clear existing handlers to avoid duplicates
        if logger.handlers:
            logger.handlers.clear()
            
        # Configure console handler
        if log_config.get("console_output", True):
            console_handler = logging.StreamHandler()
            console_format = log_config.get("console_format", 
                                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_formatter = logging.Formatter(console_format)
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
        # Configure file handler if enabled
        if log_config.get("file_output", False):
            log_file = log_config.get("log_file", f"{logger_name.lower()}.log")
            file_handler = logging.FileHandler(log_file)
            file_format = log_config.get("file_format", 
                                    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')
            file_formatter = logging.Formatter(file_format)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        # Store configured logger
        LoggingManager._configured_loggers[logger_name] = logger
            
        return logger