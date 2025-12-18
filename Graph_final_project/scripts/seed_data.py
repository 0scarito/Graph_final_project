"""ETL script to load ICIJ CSV files into Neo4j."""

import os
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

from app.database import get_database
from app.config import settings

# Chunk size for reading large CSVs
CHUNK_SIZE = 10000


def load_entities(tx, dataframe):
    """
    Load entities and create Jurisdiction nodes in a single transaction.
    Uses the 'secret sauce' pattern for Entity-Jurisdiction relationship.
    """
    query = """
    UNWIND $rows AS row
    // 1. Create the Entity
    MERGE (e:Entity {id: row.node_id})
    SET e.name = row.name, 
        e.source = row.sourceID,
        e.node_type = 'Entity'
    
    // 2. Extract and link Jurisdiction
    WITH e, row
    WHERE row.jurisdiction_description IS NOT NULL AND row.jurisdiction_description <> ''
    MERGE (j:Jurisdiction {name: row.jurisdiction_description})
    MERGE (e)-[:REGISTERED_IN]->(j)
    """
    
    # Convert DataFrame to list of dicts for Neo4j
    # Handle NaN values by converting to None
    records = dataframe.where(pd.notna(dataframe), None).to_dict('records')
    tx.run(query, rows=records)


def load_officers(tx, dataframe):
    """Load Officer nodes."""
    query = """
    UNWIND $rows AS row
    MERGE (o:Officer {id: row.node_id})
    SET o.name = row.name,
        o.node_type = 'Officer',
        o.source = row.sourceID
    """
    
    records = dataframe.where(pd.notna(dataframe), None).to_dict('records')
    tx.run(query, rows=records)


def load_intermediaries(tx, dataframe):
    """Load Intermediary nodes."""
    query = """
    UNWIND $rows AS row
    MERGE (i:Intermediary {id: row.node_id})
    SET i.name = row.name,
        i.node_type = 'Intermediary',
        i.source = row.sourceID
    """
    
    records = dataframe.where(pd.notna(dataframe), None).to_dict('records')
    tx.run(query, rows=records)


def load_addresses(tx, dataframe):
    """Load Address nodes."""
    query = """
    UNWIND $rows AS row
    MERGE (a:Address {id: row.node_id})
    SET a.address = row.address,
        a.node_type = 'Address',
        a.source = row.sourceID
    """
    
    records = dataframe.where(pd.notna(dataframe), None).to_dict('records')
    tx.run(query, rows=records)


def load_relationships(tx, dataframe):
    """Load relationships based on rel_type."""
    # Filter by relationship type and create appropriate relationships
    # Handle NaN values by filling with empty string
    rel_type_series = dataframe['rel_type'].fillna('').astype(str).str.lower().str.strip()
    
    officer_rels = dataframe[rel_type_series == 'officer_of']
    intermediary_rels = dataframe[rel_type_series == 'intermediary_of']
    address_rels = dataframe[rel_type_series == 'registered_address']
    
    # Officer relationships
    if not officer_rels.empty:
        officer_query = """
        UNWIND $rows AS row
        MATCH (o:Officer {id: row.node_id_start})
        MATCH (e:Entity {id: row.node_id_end})
        MERGE (o)-[:OFFICER_OF]->(e)
        """
        records = officer_rels.where(pd.notna(officer_rels), None).to_dict('records')
        tx.run(officer_query, rows=records)
    
    # Intermediary relationships
    if not intermediary_rels.empty:
        intermediary_query = """
        UNWIND $rows AS row
        MATCH (i:Intermediary {id: row.node_id_start})
        MATCH (e:Entity {id: row.node_id_end})
        MERGE (i)-[:INTERMEDIARY_OF]->(e)
        """
        records = intermediary_rels.where(pd.notna(intermediary_rels), None).to_dict('records')
        tx.run(intermediary_query, rows=records)
    
    # Address relationships
    if not address_rels.empty:
        address_query = """
        UNWIND $rows AS row
        MATCH (e:Entity {id: row.node_id_start})
        MATCH (a:Address {id: row.node_id_end})
        MERGE (e)-[:REGISTERED_ADDRESS]->(a)
        """
        records = address_rels.where(pd.notna(address_rels), None).to_dict('records')
        tx.run(address_query, rows=records)


def process_entities(db, data_dir: Path):
    """Process entities CSV with chunking."""
    entities_file = data_dir / "nodes-entities.csv"
    
    if not entities_file.exists():
        print(f"Warning: {entities_file} not found. Skipping...")
        return 0
    
    print("Processing entities and jurisdictions...")
    total_processed = 0
    
    with db.get_session() as session:
        for chunk_num, chunk in enumerate(pd.read_csv(entities_file, chunksize=CHUNK_SIZE, low_memory=False), 1):
            session.execute_write(load_entities, chunk)
            total_processed += len(chunk)
            
            if chunk_num % 10 == 0:
                print(f"  Processed {total_processed} entities...")
    
    print(f"✓ Processed {total_processed} entities with jurisdictions")
    return total_processed


def process_nodes(db, data_dir: Path, filename: str, load_func, node_type: str):
    """Process node CSV files with chunking."""
    file_path = data_dir / filename
    
    if not file_path.exists():
        print(f"Warning: {file_path} not found. Skipping...")
        return 0
    
    print(f"Processing {node_type} nodes...")
    total_processed = 0
    
    with db.get_session() as session:
        for chunk_num, chunk in enumerate(pd.read_csv(file_path, chunksize=CHUNK_SIZE, low_memory=False), 1):
            session.execute_write(load_func, chunk)
            total_processed += len(chunk)
            
            if chunk_num % 10 == 0:
                print(f"  Processed {total_processed} {node_type} nodes...")
    
    print(f"✓ Processed {total_processed} {node_type} nodes")
    return total_processed


def process_relationships(db, data_dir: Path):
    """Process relationships CSV with chunking."""
    relationships_file = data_dir / "relationships.csv"
    
    if not relationships_file.exists():
        print(f"Warning: {relationships_file} not found. Skipping...")
        return
    
    print("Processing relationships...")
    total_processed = 0
    
    with db.get_session() as session:
        for chunk_num, chunk in enumerate(pd.read_csv(relationships_file, chunksize=CHUNK_SIZE, low_memory=False), 1):
            session.execute_write(load_relationships, chunk)
            total_processed += len(chunk)
            
            if chunk_num % 10 == 0:
                print(f"  Processed {total_processed} relationships...")
    
    print(f"✓ Processed {total_processed} relationships")


def main():
    """Main ETL function."""
    print("Starting data ingestion...")
    print(f"Neo4j URI: {settings.neo4j_uri}")
    
    db = get_database()
    
    try:
        db.verify_connectivity()
        print("✓ Connected to Neo4j")
    except Exception as e:
        print(f"✗ Failed to connect to Neo4j: {e}")
        sys.exit(1)
    
    # Determine data directory (try both lowercase and uppercase)
    data_dir = Path("data")
    if not data_dir.exists():
        data_dir = Path("Data")  # Try uppercase
    if not data_dir.exists():
        data_dir = Path("../data")
    if not data_dir.exists():
        data_dir = Path("../Data")
    if not data_dir.exists():
        print("✗ Data directory not found. Please ensure CSV files are in ./data/ or ./Data/")
        sys.exit(1)
    
    print(f"Using data directory: {data_dir}\n")
    
    # Process entities first (creates jurisdictions too using the secret sauce pattern)
    process_entities(db, data_dir)
    
    # Process other node types
    print()
    process_nodes(db, data_dir, "nodes-officers.csv", load_officers, "Officer")
    process_nodes(db, data_dir, "nodes-intermediaries.csv", load_intermediaries, "Intermediary")
    process_nodes(db, data_dir, "nodes-addresses.csv", load_addresses, "Address")
    
    # Process relationships
    print()
    process_relationships(db, data_dir)
    
    print("\n✓ Data ingestion complete!")
    
    # Print summary statistics
    with db.get_session() as session:
        result = session.run(
            """
            MATCH (n)
            RETURN labels(n)[0] as label, count(n) as count
            ORDER BY label
            """
        )
        print("\nNode counts:")
        for record in result:
            print(f"  {record['label']}: {record['count']}")
        
        result = session.run(
            """
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(r) as count
            ORDER BY rel_type
            """
        )
        print("\nRelationship counts:")
        for record in result:
            print(f"  {record['rel_type']}: {record['count']}")


if __name__ == "__main__":
    main()
