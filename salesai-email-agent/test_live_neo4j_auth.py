import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

uri = os.getenv("NEO4J_URI", "neo4j+s://daf67124.databases.neo4j.io").strip()
password = os.getenv("NEO4J_PASSWORD", "").strip()

print(f"Testing URI: {uri}")
print(f"Password starts with: {password[:5]}... (len={len(password)})")

for user in ["neo4j", "daf67124"]:
    print(f"\n--- Testing with Username: '{user}' ---")
    for scheme in [uri, uri.replace("neo4j+s://", "bolt+s://")]:
        print(f"  Attempting {scheme}...")
        try:
            driver = GraphDatabase.driver(
                scheme,
                auth=(user, password),
                connection_timeout=5.0,
            )
            driver.verify_connectivity()
            print(f"  -> SUCCESS with user='{user}' on {scheme}!")
            with driver.session() as s:
                r = s.run("MATCH (n) RETURN count(n) AS c").single()
                print(f"  -> Total nodes in DB: {r['c']}")
            driver.close()
            break
        except Exception as e:
            print(f"  -> Failed: {type(e).__name__}: {e}")
