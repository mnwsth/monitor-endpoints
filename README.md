# Endpoint Monitoring Service

A Python-based service for monitoring HTTP endpoints and logging their status to Google Cloud Platform (GCP).

## Setup

This service uses Docker Compose for easy deployment. Follow these steps to get started:

### Prerequisites

- Docker and Docker Compose installed
- GCP service account with logging permissions. 

### Configuration

1. **Config Directory Setup**:
   The `config` directory contains:
   - `config.json` - Configuration of endpoints to monitor (uses JSON5 format)
   - `gcp-keyfile.json` - GCP service account key (optional)

2. **GCP Credentials**:
   - Rename `config/gcp-keyfile.json.example` to `config/gcp-keyfile.json`
   - Fill it with your actual GCP service account credentials

3. **Environment Variables**:
   The `.env` file contains:
   - `CONFIG_PATH` - Path to the configuration file in the container
   - `GCP_CREDENTIALS_PATH` - Path to the GCP credentials in the container
   - `CHECK_INTERVAL` - How often to check endpoints (in minutes)

## Running the Service

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## Configuration Format

The `config.json` file uses JSON5 format, which allows comments and other helpful features:

```json5
{
  // Array of endpoint objects to monitor (required)
  endpoints: [
    {
      id: "service-name",   // Unique identifier for the endpoint (optional, defaults to URL)
      url: "https://...",   // URL to monitor (required)
      method: "GET",        // HTTP method to use (optional, defaults to GET)
      headers: {            // HTTP headers to include (optional)
        Authorization: "Bearer token123"
      },
      timeout_seconds: 10,  // Request timeout in seconds (optional)
      success_status_codes: [200, 201],  // Status codes considered successful (optional)
      enabled: true         // Whether this endpoint should be monitored (optional, defaults to true)
    },
  ],
  // Default timeout if not specified in endpoint
  default_timeout_seconds: 30,
  // Default status codes if not specified in endpoint
  default_success_status_codes: [200]
}
```

### JSON5 For Configuration Specification
This configuration by default uses JSON5 format for configuration specification, which includes:
- Comments (both line and block comments)
- Trailing commas
- Unquoted property names
- Single-quoted strings
- Multi-line strings

### Disabling Endpoints

To temporarily disable monitoring for an endpoint without removing it from the configuration:

1. Add `"enabled": false` to the endpoint object
2. The service will skip disabled endpoints during checks
3. To re-enable, either remove the "enabled" flag or set it to `true`
Note: The container will have to restarted for these changes to take effect.

## Status Output Format

For each endpoint, the service produces a status object like:

```json
{
  "id": "service-name",
  "url": "https://example.com/api/health",
  "status": "OK",  // or "UNAVAILABLE"
  "response_code": 200,
  "response_time_ms": 156,
  "timestamp": "2023-06-15T12:34:56.789Z"
}
```