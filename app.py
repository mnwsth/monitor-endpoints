#!/usr/bin/env python3
"""
Endpoint Monitoring Service

This script monitors the status of HTTP endpoints defined in a configuration file
and logs their status to both console and Google Cloud Platform logging.
"""
import json
import json5
import time
import logging
import os
import sys
from typing import Dict, List, Any, Optional, Union
import requests
from datetime import datetime, timezone
import schedule
from google.cloud import logging as gcp_logging
from google.oauth2 import service_account

# Configure logging to display all log messages with timestamp and level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Create a logger for this application
logger = logging.getLogger("endpoint_monitor")

class EndpointMonitor:
    """
    A service that monitors HTTP endpoints and logs their status.
    
    This class handles the monitoring of HTTP endpoints defined in a configuration file.
    It periodically checks each endpoint and logs whether it's available or not.
    Results can be logged to both the console and Google Cloud Platform logging.
    """
    
    def __init__(self, config_path: str, gcp_credentials_path: Optional[str] = None):
        """
        Initialize the endpoint monitor.
        
        Args:
            config_path: Path to the JSON configuration file
            gcp_credentials_path: Path to the GCP service account key file (optional)
        """
        # Load the configuration from the specified file
        self.config = self._load_config(config_path)
        
        # Setup Google Cloud Platform logging if credentials are provided
        self.gcp_client = self._setup_gcp_logging(gcp_credentials_path)
        self.gcp_logger = None
        
        # Create a logger for GCP if the client was successfully initialized
        if self.gcp_client:
            self.gcp_logger = self.gcp_client.logger('endpoint_monitor')
            
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load the configuration file containing endpoint definitions.
        
        The configuration file should be in JSON5 format with the following structure:
        
        {
          "endpoints": [              // Array of endpoint objects to monitor (required)
            {
              "id": "service-name",   // Unique identifier for the endpoint (optional, defaults to URL)
              "url": "https://...",   // URL to monitor (required)
              "method": "GET",        // HTTP method to use (optional, defaults to GET)
              "headers": {            // HTTP headers to include (optional)
                "Authorization": "Bearer token123"
              },
              "timeout_seconds": 10,  // Request timeout in seconds (optional)
              "success_status_codes": [200, 201],  // Status codes considered successful (optional)
              "enabled": true         // Whether this endpoint should be monitored (optional, defaults to true)
            }
          ],
          "default_timeout_seconds": 30,          // Default timeout if not specified in endpoint (optional, defaults to 30)
          "default_success_status_codes": [200]   // Default status codes if not specified in endpoint (optional, defaults to [200])
        }
        
        JSON5 format allows for comments and other features like trailing commas,
        single quotes, and unquoted keys.
        
        Args:
            config_path: Path to the JSON5 configuration file
            
        Returns:
            The loaded configuration as a dictionary
            
        Raises:
            Exception: If the configuration file can't be loaded
        """
        try:
            # Open and parse the JSON5 configuration file
            with open(config_path, 'r') as config_file:
                config = json5.load(config_file)
                
            # Log how many endpoints were found in the configuration
            endpoint_count = len(config.get('endpoints', []))
            logger.info(f"Loaded configuration with {endpoint_count} endpoints")
            
            return config
        except Exception as error:
            # Log the error and re-raise it
            logger.error(f"Failed to load configuration file: {str(error)}")
            raise

    def _setup_gcp_logging(self, gcp_credentials_path: Optional[str]) -> Optional[gcp_logging.Client]:
        """
        Setup Google Cloud Platform logging client.
        
        Args:
            gcp_credentials_path: Path to the GCP service account key file
            
        Returns:
            The GCP logging client if successfully initialized, None otherwise
        """
        # Check if credentials path is provided and file exists
        if not gcp_credentials_path or not os.path.exists(gcp_credentials_path):
            logger.warning("GCP credentials not provided or credentials file doesn't exist. GCP logging is disabled.")
            return None
        
        try:
            # Create GCP credentials from the service account file
            credentials = service_account.Credentials.from_service_account_file(
                gcp_credentials_path
            )
            
            # Initialize the GCP logging client with the credentials
            gcp_client = gcp_logging.Client(credentials=credentials)
            logger.info("GCP logging client initialized successfully")
            
            return gcp_client
        
        except Exception as error:
            # Log the error and return None to indicate GCP logging is unavailable
            logger.error(f"Failed to initialize GCP logging: {str(error)}")
            return None

    def _get_endpoint_defaults(self) -> Dict[str, Any]:
        """
        Get the default configuration values for endpoints.
        
        Returns:
            A dictionary containing default values for timeout and success status codes
        """
        return {
            'timeout': self.config.get('default_timeout_seconds', 30),
            'success_codes': self.config.get('default_success_status_codes', [200])
        }

    def check_endpoint(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check a single endpoint and determine its status.
        
        Args:
            endpoint: The endpoint configuration dictionary
            
        Returns:
            A status dictionary containing the result of the check
        """
        # Extract endpoint details with defaults for optional fields
        endpoint_id = endpoint.get('id', endpoint['url'])
        url = endpoint['url']
        method = endpoint.get('method', 'GET')
        headers = endpoint.get('headers', {})
        
        # Get default values from configuration
        defaults = self._get_endpoint_defaults()
        
        # Use endpoint-specific values if provided, otherwise use defaults
        timeout = endpoint.get('timeout_seconds', defaults['timeout'])
        success_codes = endpoint.get('success_status_codes', defaults['success_codes'])
        
        # Record start time to calculate response time
        start_time = time.time()
        
        try:
            # Make the HTTP request to check the endpoint
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=timeout
            )
            
            # Calculate response time in milliseconds
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Determine status based on the HTTP status code
            is_successful = response.status_code in success_codes
            status = "OK" if is_successful else "UNAVAILABLE"
            
            # Create the result dictionary
            result = {
                "id": endpoint_id,
                "url": url,
                "status": status,
                "response_code": response.status_code,
                "response_time_ms": response_time_ms,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            return result
            
        except requests.RequestException as error:
            # If the request fails for any reason, mark as UNAVAILABLE
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Create the result dictionary with error information
            result = {
                "id": endpoint_id,
                "url": url,
                "status": "UNAVAILABLE",
                "error": str(error),
                "response_time_ms": response_time_ms,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            return result

    def _log_result(self, result: Dict[str, Any]) -> None:
        """
        Log a single endpoint check result to console and GCP (if configured).
        
        Args:
            result: The endpoint check result dictionary
        """
        # Determine the appropriate log level based on status
        is_available = result['status'] == 'OK'
        log_level = logging.INFO if is_available else logging.ERROR
        
        # Log to console
        log_message = f"Endpoint {result['id']}: {result['status']}"
        logger.log(log_level, log_message)
        
        # Log to GCP if configured
        if self.gcp_logger:
            # Determine the GCP severity level based on status
            severity = 'INFO' if is_available else 'ERROR'
            
            # Log the structured data to GCP
            self.gcp_logger.log_struct(
                result,
                severity=severity
            )

    def check_all_endpoints(self) -> List[Dict[str, Any]]:
        """
        Check all endpoints defined in the configuration and log their status.
        
        Returns:
            A list of status dictionaries for all endpoints
        """
        logger.info("Starting endpoint status checks")
        results = []
        
        # Get the list of endpoints from the configuration
        all_endpoints = self.config.get('endpoints', [])
        
        # Filter out disabled endpoints
        enabled_endpoints = [ep for ep in all_endpoints if ep.get('enabled', True)]
        
        if len(enabled_endpoints) < len(all_endpoints):
            logger.info(f"Skipping {len(all_endpoints) - len(enabled_endpoints)} disabled endpoints")
        
        # Check each enabled endpoint
        for endpoint in enabled_endpoints:
            # Get the status of the endpoint
            result = self.check_endpoint(endpoint)
            
            # Add the result to the list
            results.append(result)
            
            # Log the result
            self._log_result(result)
        
        logger.info(f"Completed checking {len(enabled_endpoints)} endpoints")
        return results

    def start_monitoring(self, interval_minutes: int = 5) -> None:
        """
        Start monitoring endpoints at the specified interval.
        
        This method will run forever, periodically checking all endpoints.
        
        Args:
            interval_minutes: How often to check the endpoints (in minutes)
        """
        logger.info(f"Starting monitoring service with {interval_minutes} minute interval")
        
        # Run once immediately when the service starts
        self.check_all_endpoints()
        
        # Schedule regular checks at the specified interval
        schedule.every(interval_minutes).minutes.do(self.check_all_endpoints)
        
        logger.info(f"Monitoring scheduled every {interval_minutes} minutes")
        
        # Keep the script running and check for scheduled tasks
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Monitoring service stopped by user")


def main():
    """
    Main entry point for the application.
    
    Reads configuration paths from environment variables and starts the monitoring service.
    """
    # Get configuration paths from environment variables or use defaults
    config_path = os.environ.get('CONFIG_PATH', '/app/config/config.json')
    gcp_credentials_path = os.environ.get('GCP_CREDENTIALS_PATH')
    check_interval = int(os.environ.get('CHECK_INTERVAL', 5))
    
    # Log the paths being used
    logger.info(f"Using configuration file: {config_path}")
    logger.info(f"GCP credentials path: {gcp_credentials_path or 'Not provided'}")
    logger.info(f"Check interval: {check_interval} minutes")
    
    # Create and start the monitor
    monitor = EndpointMonitor(config_path, gcp_credentials_path)
    monitor.start_monitoring(interval_minutes=check_interval)


if __name__ == "__main__":
    main() 