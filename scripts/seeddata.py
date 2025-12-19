#!/usr/bin/env python3
"""
Panama Papers Neo4j Data Import Script (Simplified)
====================================================
Imports ICIJ Offshore Leaks CSV data into Neo4j.

Usage:
    python scripts/seeddata.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from neo4j import GraphDatabase

# Load environment variables
load_dotenv()

# Configuration - Always use localhost for local scripts
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Force localhost if running locally
if "neo4j:" in NEO4J_URI:
    NEO4J_URI = "bolt://localhost:7687"
    print(f"[INFO] Overriding URI to {NEO4J_URI} for local execution")

DATA_DIR = Path(__file__).parent.parent / "data"
BATCH_SIZE = 1000

# CSV file mappings
CSV_FILES = {
    "entities": "nodes-entities.csv",
    "officers": "nodes-officers.csv",
    "intermediaries": "nodes-intermediaries.csv",
    "addresses": "nodes-addresses.csv",
    "relationships": "relationships.csv",
}


def connect():
    """Connect to Neo4j."""
    if not NEO4J_PASSWORD:
        print("[ERROR] NEO4J_PASSWORD not set in .env file")
        sys.exit(1)
    
    print(f"[INFO] Connecting to Neo4j at {NEO4J_URI}...")
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("[INFO] ✓ Connected to Neo4j")
        return driver
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        sys.exit(1)


def create_constraints(driver):
    """Create uniqueness constraints."""
    print("[INFO] Creating constraints...")
    
    constraints = [
        "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
        "CREATE CONSTRAINT officer_id_unique IF NOT EXISTS FOR (o:Officer) REQUIRE o.officer_id IS UNIQUE",
        "CREATE CONSTRAINT intermediary_id_unique IF NOT EXISTS FOR (i:Intermediary) REQUIRE i.intermediary_id IS UNIQUE",
        "CREATE CONSTRAINT address_id_unique IF NOT EXISTS FOR (a:Address) REQUIRE a.address_id IS UNIQUE",
    ]
    
    with driver.session(database=NEO4J_DATABASE) as session:
        for constraint in constraints:
            try:
                session.run(constraint)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    print(f"[WARN] Constraint issue: {e}")
    
    print("[INFO] ✓ Constraints created")


def load_entities(driver):
    """Load Entity nodes."""
    csv_path = DATA_DIR / CSV_FILES["entities"]
    if not csv_path.exists():
        print(f"[WARN] {csv_path} not found, skipping entities")
        return 0
    
    print(f"[INFO] Loading entities from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    df = df.where(pd.notnull(df), None)
    
    # Determine ID column name
    id_col = "node_id" if "node_id" in df.columns else "entity_id" if "entity_id" in df.columns else df.columns[0]
    
    query = """
    UNWIND $batch AS row
    MERGE (e:Entity {entity_id: row.id})
    SET e.name = row.name,
        e.jurisdiction_code = row.jurisdiction,
        e.status = row.status,
        e.source = row.sourceID,
        e.incorporation_date = row.incorporation_date,
        e.inactivation_date = row.inactivation_date
    """
    
    count = 0
    with driver.session(database=NEO4J_DATABASE) as session:
        for i in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[i:i+BATCH_SIZE]
            records = []
            for _, row in batch.iterrows():
                records.append({
                    "id": str(row.get(id_col, "")),
                    "name": row.get("name"),
                    "jurisdiction": row.get("jurisdiction") or row.get("jurisdiction_code"),
                    "status": row.get("status"),
                    "sourceID": row.get("sourceID") or row.get("source"),
                    "incorporation_date": row.get("incorporation_date"),
                    "inactivation_date": row.get("inactivation_date"),
                })
            session.run(query, batch=records)
            count += len(records)
            print(f"[INFO]   Processed {count:,} entities...", end="\r")
    
    print(f"[INFO] ✓ Loaded {count:,} entities            ")
    return count


def load_officers(driver):
    """Load Officer nodes."""
    csv_path = DATA_DIR / CSV_FILES["officers"]
    if not csv_path.exists():
        print(f"[WARN] {csv_path} not found, skipping officers")
        return 0
    
    print(f"[INFO] Loading officers from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    df = df.where(pd.notnull(df), None)
    
    id_col = "node_id" if "node_id" in df.columns else "officer_id" if "officer_id" in df.columns else df.columns[0]
    
    query = """
    UNWIND $batch AS row
    MERGE (o:Officer {officer_id: row.id})
    SET o.name = row.name,
        o.country_codes = row.country_codes,
        o.source = row.sourceID
    """
    
    count = 0
    with driver.session(database=NEO4J_DATABASE) as session:
        for i in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[i:i+BATCH_SIZE]
            records = []
            for _, row in batch.iterrows():
                records.append({
                    "id": str(row.get(id_col, "")),
                    "name": row.get("name"),
                    "country_codes": row.get("country_codes") or row.get("countries"),
                    "sourceID": row.get("sourceID") or row.get("source"),
                })
            session.run(query, batch=records)
            count += len(records)
            print(f"[INFO]   Processed {count:,} officers...", end="\r")
    
    print(f"[INFO] ✓ Loaded {count:,} officers            ")
    return count


def load_intermediaries(driver):
    """Load Intermediary nodes."""
    csv_path = DATA_DIR / CSV_FILES["intermediaries"]
    if not csv_path.exists():
        print(f"[WARN] {csv_path} not found, skipping intermediaries")
        return 0
    
    print(f"[INFO] Loading intermediaries from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    df = df.where(pd.notnull(df), None)
    
    id_col = "node_id" if "node_id" in df.columns else "intermediary_id" if "intermediary_id" in df.columns else df.columns[0]
    
    query = """
    UNWIND $batch AS row
    MERGE (i:Intermediary {intermediary_id: row.id})
    SET i.name = row.name,
        i.country_codes = row.country_codes,
        i.source = row.sourceID
    """
    
    count = 0
    with driver.session(database=NEO4J_DATABASE) as session:
        for i in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[i:i+BATCH_SIZE]
            records = []
            for _, row in batch.iterrows():
                records.append({
                    "id": str(row.get(id_col, "")),
                    "name": row.get("name"),
                    "country_codes": row.get("country_codes") or row.get("countries"),
                    "sourceID": row.get("sourceID") or row.get("source"),
                })
            session.run(query, batch=records)
            count += len(records)
            print(f"[INFO]   Processed {count:,} intermediaries...", end="\r")
    
    print(f"[INFO] ✓ Loaded {count:,} intermediaries      ")
    return count


def load_addresses(driver):
    """Load Address nodes."""
    csv_path = DATA_DIR / CSV_FILES["addresses"]
    if not csv_path.exists():
        print(f"[WARN] {csv_path} not found, skipping addresses")
        return 0
    
    print(f"[INFO] Loading addresses from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    df = df.where(pd.notnull(df), None)
    
    id_col = "node_id" if "node_id" in df.columns else "address_id" if "address_id" in df.columns else df.columns[0]
    
    query = """
    UNWIND $batch AS row
    MERGE (a:Address {address_id: row.id})
    SET a.address = row.address,
        a.country_codes = row.country_codes,
        a.source = row.sourceID
    """
    
    count = 0
    with driver.session(database=NEO4J_DATABASE) as session:
        for i in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[i:i+BATCH_SIZE]
            records = []
            for _, row in batch.iterrows():
                records.append({
                    "id": str(row.get(id_col, "")),
                    "address": row.get("address") or row.get("name"),
                    "country_codes": row.get("country_codes") or row.get("countries"),
                    "sourceID": row.get("sourceID") or row.get("source"),
                })
            session.run(query, batch=records)
            count += len(records)
            print(f"[INFO]   Processed {count:,} addresses...", end="\r")
    
    print(f"[INFO] ✓ Loaded {count:,} addresses           ")
    return count


def load_relationships(driver):
    """Load relationships between nodes."""
    csv_path = DATA_DIR / CSV_FILES["relationships"]
    if not csv_path.exists():
        print(f"[WARN] {csv_path} not found, skipping relationships")
        return 0
    
    print(f"[INFO] Loading relationships from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    df = df.where(pd.notnull(df), None)
    
    # ICIJ uses START_ID, END_ID, TYPE columns
    start_col = "START_ID" if "START_ID" in df.columns else "start_id" if "start_id" in df.columns else "node_id_start"
    end_col = "END_ID" if "END_ID" in df.columns else "end_id" if "end_id" in df.columns else "node_id_end"
    type_col = "TYPE" if "TYPE" in df.columns else "rel_type" if "rel_type" in df.columns else "type"
    
    query = """
    UNWIND $batch AS row
    MATCH (start) WHERE start.entity_id = row.start_id 
                     OR start.officer_id = row.start_id 
                     OR start.intermediary_id = row.start_id 
                     OR start.address_id = row.start_id
    MATCH (end) WHERE end.entity_id = row.end_id 
                   OR end.officer_id = row.end_id 
                   OR end.intermediary_id = row.end_id 
                   OR end.address_id = row.end_id
    CALL apoc.merge.relationship(start, row.rel_type, {}, {}, end, {}) YIELD rel
    RETURN count(rel)
    """
    
    # Fallback query without APOC
    fallback_query = """
    UNWIND $batch AS row
    MATCH (start) WHERE start.entity_id = row.start_id 
                     OR start.officer_id = row.start_id 
                     OR start.intermediary_id = row.start_id 
                     OR start.address_id = row.start_id
    MATCH (end) WHERE end.entity_id = row.end_id 
                   OR end.officer_id = row.end_id 
                   OR end.intermediary_id = row.end_id 
                   OR end.address_id = row.end_id
    MERGE (start)-[r:CONNECTED_TO]->(end)
    SET r.type = row.rel_type
    RETURN count(r)
    """
    
    count = 0
    with driver.session(database=NEO4J_DATABASE) as session:
        # Test if APOC is available
        try:
            session.run("RETURN apoc.version()").single()
            use_apoc = True
            print("[INFO] Using APOC for dynamic relationship types")
        except:
            use_apoc = False
            print("[INFO] APOC not available, using generic CONNECTED_TO relationships")
        
        active_query = query if use_apoc else fallback_query
        
        for i in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[i:i+BATCH_SIZE]
            records = []
            for _, row in batch.iterrows():
                records.append({
                    "start_id": str(row.get(start_col, "")),
                    "end_id": str(row.get(end_col, "")),
                    "rel_type": row.get(type_col) or "CONNECTED_TO",
                })
            try:
                session.run(active_query, batch=records)
            except Exception as e:
                if "apoc" in str(e).lower():
                    session.run(fallback_query, batch=records)
            count += len(records)
            print(f"[INFO]   Processed {count:,} relationships...", end="\r")
    
    print(f"[INFO] ✓ Loaded {count:,} relationships       ")
    return count


def verify_import(driver):
    """Verify the import by counting nodes."""
    print("\n[INFO] Verifying import...")
    
    queries = [
        ("Entity", "MATCH (n:Entity) RETURN count(n) AS count"),
        ("Officer", "MATCH (n:Officer) RETURN count(n) AS count"),
        ("Intermediary", "MATCH (n:Intermediary) RETURN count(n) AS count"),
        ("Address", "MATCH (n:Address) RETURN count(n) AS count"),
        ("Relationships", "MATCH ()-[r]->() RETURN count(r) AS count"),
    ]
    
    with driver.session(database=NEO4J_DATABASE) as session:
        print("\n" + "=" * 40)
        print("         IMPORT SUMMARY")
        print("=" * 40)
        for label, query in queries:
            result = session.run(query).single()
            count = result["count"] if result else 0
            print(f"  {label:15} : {count:>10,}")
        print("=" * 40)


def main():
    """Main entry point."""
    print("=" * 60)
    print("  PANAMA PAPERS DATA IMPORT")
    print("=" * 60)
    print(f"  Data directory: {DATA_DIR}")
    print(f"  Batch size: {BATCH_SIZE:,}")
    print("=" * 60)
    
    # Check data directory
    if not DATA_DIR.exists():
        print(f"[ERROR] Data directory not found: {DATA_DIR}")
        sys.exit(1)
    
    # Connect
    driver = connect()
    
    try:
        # Create constraints
        create_constraints(driver)
        
        # Load nodes
        load_entities(driver)
        load_officers(driver)
        load_intermediaries(driver)
        load_addresses(driver)
        
        # Load relationships
        load_relationships(driver)
        
        # Verify
        verify_import(driver)
        
        print("\n[INFO] ✓ Import completed successfully!")
        
    except Exception as e:
        print(f"\n[ERROR] Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        driver.close()


if __name__ == "__main__":
    main()
