"""Read-only evaluation fixture, not production application code."""
DATABASE_ENGINE = "postgresql"
POD_COUNT = 3

def deliver(payload, destination, http_client):
    # Current code makes one request; no durable delivery identifier or retries.
    return http_client.post(destination, json=payload, timeout=5)
