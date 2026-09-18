"""Read-only Neo4j connectivity check.

Run from salesai-email-agent with the virtual environment activated:
    python test_neo4j_connection.py
"""

from app.neo4j_client import neo4j_client


if not neo4j_client.configured:
    print("FAIL: NEO4J_URI, NEO4J_USERNAME, or NEO4J_PASSWORD is missing")
    raise SystemExit(1)

if neo4j_client.verify_connectivity():
    print(f"PASS: Neo4j connectivity verified for database {neo4j_client.database}")
else:
    print("FAIL: Neo4j connectivity could not be verified")
    raise SystemExit(1)

neo4j_client.close()