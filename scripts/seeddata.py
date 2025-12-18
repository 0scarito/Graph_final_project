#!/usr/bin/env python3
"""
Panama Papers Neo4j Data Import Script
=======================================

Imports ICIJ Offshore Leaks CSV data into Neo4j 5.x database.

Data Sources:
    - ICIJ Offshore Leaks Database: https://offshoreleaks.icij.org/pages/database

Usage:
    python seeddata.py
    python seeddata.py --data-dir ./data --batch-size 5000
    python seeddata.py --verify-only

Environment Variables (via .env file):
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=your_secure_password
    NEO4J_DATABASE=neo4j

Author: Panama Papers Analysis Platform
Version: 1.0.0
Python: 3.11+
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field

import pandas as pd
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import (
    ServiceUnavailable,
    AuthError,
    ConstraintError,
    TransientError,
    DatabaseError,
)
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from .env file
load_dotenv()

# Neo4j connection settings
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Import settings
DEFAULT_BATCH_SIZE = 1000
DEFAULT_DATA_DIR = "./data"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

# CSV file names (ICIJ format)
CSV_FILES = {
    "entities": "nodes-entities.csv",
    "officers": "nodes-officers.csv",
    "intermediaries": "nodes-intermediaries.csv",
    "addresses": "nodes-addresses.csv",
    "relationships": "relationships.csv",
}


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Configure logging with console and optional file output."""
    logger = logging.getLogger("panama_import")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        "%(asctime)s │ %(levelname)-8s │ %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(funcName)s - %(message)s"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


logger = setup_logging()


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ImportStats:
    """Track import statistics."""
    entities_created: int = 0
    entities_skipped: int = 0
    officers_created: int = 0
    officers_skipped: int = 0
    intermediaries_created: int = 0
    intermediaries_skipped: int = 0
    addresses_created: int = 0
    addresses_skipped: int = 0
    relationships_created: int = 0
    relationships_skipped: int = 0
    errors: list = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    def summary(self) -> str:
        """Generate summary report."""
        self.end_time = datetime.now()
        duration = self.end_time - self.start_time

        return f"""
╔══════════════════════════════════════════════════════════════╗
║                    IMPORT SUMMARY                             ║
╠══════════════════════════════════════════════════════════════╣
║  Node Type       │  Created    │  Skipped    │  Total        ║
╠──────────────────┼─────────────┼─────────────┼───────────────╣
║  Entities        │  {self.entities_created:>9,}  │  {self.entities_skipped:>9,}  │  {self.entities_created + self.entities_skipped:>11,}  ║
║  Officers        │  {self.officers_created:>9,}  │  {self.officers_skipped:>9,}  │  {self.officers_created + self.officers_skipped:>11,}  ║
║  Intermediaries  │  {self.intermediaries_created:>9,}  │  {self.intermediaries_skipped:>9,}  │  {self.intermediaries_created + self.intermediaries_skipped:>11,}  ║
║  Addresses       │  {self.addresses_created:>9,}  │  {self.addresses_skipped:>9,}  │  {self.addresses_created + self.addresses_skipped:>11,}  ║
╠──────────────────┼─────────────┼─────────────┼───────────────╣
║  Relationships   │  {self.relationships_created:>9,}  │  {self.relationships_skipped:>9,}  │  {self.relationships_created + self.relationships_skipped:>11,}  ║
╠══════════════════════════════════════════════════════════════╣
║  Duration: {str(duration).split('.')[0]:>15}                              ║
║  Errors:   {len(self.errors):>15,}                              ║
╚══════════════════════════════════════════════════════════════╝
"""


# ============================================================================
# DATABASE CONNECTION
# ============================================================================

async def connect_neo4j(
    uri: str = NEO4J_URI,
    user: str = NEO4J_USER,
    password: str = NEO4J_PASSWORD,
    database: str = NEO4J_DATABASE,
) -> AsyncDriver:
    """
    Establish async connection to Neo4j database.

    Args:
        uri: Bolt URI for Neo4j instance
        user: Database username
        password: Database password
        database: Target database name

    Returns:
        AsyncDriver instance

    Raises:
        ServiceUnavailable: If Neo4j is not reachable
        AuthError: If credentials are invalid
    """
    if not password:
        raise ValueError(
            "NEO4J_PASSWORD not set. Create a .env file with:\n"
            "NEO4J_URI=bolt://localhost:7687\n"
            "NEO4J_USER=neo4j\n"
            "NEO4J_PASSWORD=your_password"
        )

    logger.info(f"Connecting to Neo4j at {uri}...")

    try:
        driver = AsyncGraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60,
        )

        # Verify connectivity
        await driver.verify_connectivity()

        # Get server info
        async with driver.session(database=database) as session:
            result = await session.run("CALL dbms.components() YIELD name, versions")
            record = await result.single()
            version = record["versions"][0] if record else "unknown"

        logger.info(f"✓ Connected to Neo4j {version}")
        return driver

    except ServiceUnavailable as e:
        logger.error(f"✗ Neo4j not available at {uri}: {e}")
        raise
    except AuthError as e:
        logger.error(f"✗ Authentication failed: {e}")
        raise


async def close_connection(driver: AsyncDriver) -> None:
    """Safely close the Neo4j driver connection."""
    if driver:
        await driver.close()
        logger.info("✓ Neo4j connection closed")


# ============================================================================
# DATA CLEANING UTILITIES
# ============================================================================

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and prepare DataFrame for Neo4j import.

    - Replace NaN with None (Neo4j compatible)
    - Strip whitespace from strings
    - Convert dates to ISO format
    """
    # Replace NaN with None
    df = df.where(pd.notnull(df), None)

    # Strip whitespace from string columns
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

    return df


def parse_date(date_str: Any) -> Optional[str]:
    """
    Parse various date formats to ISO format string.

    Handles:
        - Full dates: 2010-05-15
        - Partial dates: 2010-05 or 2010
        - Empty/null values
    """
    if date_str is None or pd.isna(date_str):
        return None

    date_str = str(date_str).strip()

    if not date_str or date_str.lower() in ("", "nan", "none", "null"):
        return None

    # Try parsing different formats
    for fmt in ["%Y-%m-%d", "%d-%b-%Y", "%Y-%m", "%Y", "%d/%m/%Y", "%m/%d/%Y"]:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Return original if can't parse
    return date_str[:10] if len(date_str) >= 10 else None


def prepare_records(df: pd.DataFrame, date_columns: list[str] = None) -> list[dict]:
    """
    Convert DataFrame to list of dicts with proper date handling.

    Args:
        df: Source DataFrame
        date_columns: List of columns containing dates

    Returns:
        List of dictionaries ready for Neo4j import
    """
    df = clean_dataframe(df.copy())

    # Parse date columns
    if date_columns:
        for col in date_columns:
            if col in df.columns:
                df[col] = df[col].apply(parse_date)

    # Convert to records
    records = df.to_dict("records")

    # Replace remaining NaN with None (safety check)
    for record in records:
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None

    return records


# ============================================================================
# NODE IMPORT FUNCTIONS
# ============================================================================

async def load_entities(
    driver: AsyncDriver,
    csv_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    stats: ImportStats = None,
) -> int:
    """
    Load Entity nodes from ICIJ CSV.

    CSV columns expected:
        - node_id (or entity_id)
        - name
        - jurisdiction
        - jurisdiction_description
        - incorporation_date
        - inactivation_date
        - struck_off_date
        - status
        - sourceID

    Args:
        driver: Neo4j async driver
        csv_path: Path to entities CSV file
        batch_size: Number of records per transaction
        stats: ImportStats object for tracking

    Returns:
        Number of entities created
    """
    logger.info(f"Loading entities from {csv_path}...")

    if not csv_path.exists():
        logger.warning(f"⚠ Entities file not found: {csv_path}")
        return 0

    try:
        df = pd.read_csv(csv_path, low_memory=False)
        logger.info(f"  Found {len(df):,} entity records")

        # Normalize column names (ICIJ uses different formats)
        column_map = {
            "node_id": "entity_id",
            "jurisdiction_description": "jurisdiction_name",
            "sourceID": "source",
        }
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

        # Ensure entity_id exists
        if "entity_id" not in df.columns:
            logger.error("✗ Missing required column: entity_id or node_id")
            return 0

        # Prepare records with date parsing
        date_cols = ["incorporation_date", "inactivation_date", "struck_off_date"]
        records = prepare_records(df, date_columns=date_cols)

        created = 0
        skipped = 0

        # Batch import with MERGE (upsert)
        query = """
        UNWIND $batch AS row
        MERGE (e:Entity {entity_id: row.entity_id})
        ON CREATE SET
            e.name = row.name,
            e.jurisdiction_code = row.jurisdiction,
            e.jurisdiction_name = row.jurisdiction_name,
            e.incorporation_date = CASE 
                WHEN row.incorporation_date IS NOT NULL 
                THEN date(row.incorporation_date) 
                ELSE NULL 
            END,
            e.inactivation_date = CASE 
                WHEN row.inactivation_date IS NOT NULL 
                THEN date(row.inactivation_date) 
                ELSE NULL 
            END,
            e.struck_off_date = CASE 
                WHEN row.struck_off_date IS NOT NULL 
                THEN date(row.struck_off_date) 
                ELSE NULL 
            END,
            e.status = row.status,
            e.source = row.source,
            e.entity_type = COALESCE(row.type, 'Unknown'),
            e.created_at = datetime()
        ON MATCH SET
            e.updated_at = datetime()
        RETURN 
            count(CASE WHEN e.created_at = datetime() THEN 1 END) AS created,
            count(CASE WHEN e.updated_at = datetime() THEN 1 END) AS updated
        """

        async with driver.session(database=NEO4J_DATABASE) as session:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]

                try:
                    result = await session.run(query, batch=batch)
                    summary = await result.consume()
                    created += summary.counters.nodes_created
                    skipped += len(batch) - summary.counters.nodes_created

                    if (i + batch_size) % (batch_size * 10) == 0 or i + batch_size >= len(records):
                        progress = min(i + batch_size, len(records))
                        logger.info(f"  Progress: {progress:,}/{len(records):,} entities ({progress * 100 // len(records)}%)")

                except TransientError as e:
                    logger.warning(f"  ⚠ Transient error, retrying batch: {e}")
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    # Retry once
                    result = await session.run(query, batch=batch)
                    await result.consume()

        logger.info(f"✓ Entities: {created:,} created, {skipped:,} already existed")

        if stats:
            stats.entities_created = created
            stats.entities_skipped = skipped

        return created

    except Exception as e:
        logger.error(f"✗ Entity import failed: {e}")
        if stats:
            stats.errors.append(f"Entity import: {e}")
        raise


async def load_officers(
    driver: AsyncDriver,
    csv_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    stats: ImportStats = None,
) -> int:
    """
    Load Officer/Person nodes from ICIJ CSV.

    CSV columns expected:
        - node_id (or officer_id)
        - name
        - countries (nationality)
        - sourceID
    """
    logger.info(f"Loading officers from {csv_path}...")

    if not csv_path.exists():
        logger.warning(f"⚠ Officers file not found: {csv_path}")
        return 0

    try:
        df = pd.read_csv(csv_path, low_memory=False)
        logger.info(f"  Found {len(df):,} officer records")

        # Normalize columns
        column_map = {
            "node_id": "officer_id",
            "countries": "nationality",
            "sourceID": "source",
        }
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

        if "officer_id" not in df.columns:
            logger.error("✗ Missing required column: officer_id or node_id")
            return 0

        records = prepare_records(df)

        query = """
        UNWIND $batch AS row
        MERGE (p:Person:Officer {person_id: row.officer_id})
        ON CREATE SET
            p.full_name = row.name,
            p.nationality = row.nationality,
            p.source = row.source,
            p.created_at = datetime()
        ON MATCH SET
            p.updated_at = datetime()
        """

        created = 0
        skipped = 0

        async with driver.session(database=NEO4J_DATABASE) as session:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]

                result = await session.run(query, batch=batch)
                summary = await result.consume()
                created += summary.counters.nodes_created
                skipped += len(batch) - summary.counters.nodes_created

                if (i + batch_size) % (batch_size * 10) == 0 or i + batch_size >= len(records):
                    progress = min(i + batch_size, len(records))
                    logger.info(f"  Progress: {progress:,}/{len(records):,} officers ({progress * 100 // len(records)}%)")

        logger.info(f"✓ Officers: {created:,} created, {skipped:,} already existed")

        if stats:
            stats.officers_created = created
            stats.officers_skipped = skipped

        return created

    except Exception as e:
        logger.error(f"✗ Officer import failed: {e}")
        if stats:
            stats.errors.append(f"Officer import: {e}")
        raise


async def load_intermediaries(
    driver: AsyncDriver,
    csv_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    stats: ImportStats = None,
) -> int:
    """
    Load Intermediary nodes from ICIJ CSV.

    CSV columns expected:
        - node_id (or intermediary_id)
        - name
        - countries (jurisdiction)
        - status
        - sourceID
    """
    logger.info(f"Loading intermediaries from {csv_path}...")

    if not csv_path.exists():
        logger.warning(f"⚠ Intermediaries file not found: {csv_path}")
        return 0

    try:
        df = pd.read_csv(csv_path, low_memory=False)
        logger.info(f"  Found {len(df):,} intermediary records")

        column_map = {
            "node_id": "intermediary_id",
            "countries": "country_code",
            "sourceID": "source",
        }
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

        if "intermediary_id" not in df.columns:
            logger.error("✗ Missing required column: intermediary_id or node_id")
            return 0

        records = prepare_records(df)

        query = """
        UNWIND $batch AS row
        MERGE (i:Intermediary {intermediary_id: row.intermediary_id})
        ON CREATE SET
            i.name = row.name,
            i.country_code = row.country_code,
            i.status = row.status,
            i.source = row.source,
            i.created_at = datetime()
        ON MATCH SET
            i.updated_at = datetime()
        """

        created = 0
        skipped = 0

        async with driver.session(database=NEO4J_DATABASE) as session:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]

                result = await session.run(query, batch=batch)
                summary = await result.consume()
                created += summary.counters.nodes_created
                skipped += len(batch) - summary.counters.nodes_created

                if (i + batch_size) % (batch_size * 10) == 0 or i + batch_size >= len(records):
                    progress = min(i + batch_size, len(records))
                    logger.info(f"  Progress: {progress:,}/{len(records):,} intermediaries ({progress * 100 // len(records)}%)")

        logger.info(f"✓ Intermediaries: {created:,} created, {skipped:,} already existed")

        if stats:
            stats.intermediaries_created = created
            stats.intermediaries_skipped = skipped

        return created

    except Exception as e:
        logger.error(f"✗ Intermediary import failed: {e}")
        if stats:
            stats.errors.append(f"Intermediary import: {e}")
        raise


async def load_addresses(
    driver: AsyncDriver,
    csv_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    stats: ImportStats = None,
) -> int:
    """
    Load Address nodes from ICIJ CSV.

    CSV columns expected:
        - node_id (or address_id)
        - address
        - countries
        - sourceID
    """
    logger.info(f"Loading addresses from {csv_path}...")

    if not csv_path.exists():
        logger.warning(f"⚠ Addresses file not found: {csv_path}")
        return 0

    try:
        df = pd.read_csv(csv_path, low_memory=False)
        logger.info(f"  Found {len(df):,} address records")

        column_map = {
            "node_id": "address_id",
            "address": "full_address",
            "countries": "country_code",
            "sourceID": "source",
        }
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

        if "address_id" not in df.columns:
            logger.error("✗ Missing required column: address_id or node_id")
            return 0

        records = prepare_records(df)

        query = """
        UNWIND $batch AS row
        MERGE (a:Address {address_id: row.address_id})
        ON CREATE SET
            a.full_address = row.full_address,
            a.country_code = row.country_code,
            a.source = row.source,
            a.created_at = datetime()
        ON MATCH SET
            a.updated_at = datetime()
        """

        created = 0
        skipped = 0

        async with driver.session(database=NEO4J_DATABASE) as session:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]

                result = await session.run(query, batch=batch)
                summary = await result.consume()
                created += summary.counters.nodes_created
                skipped += len(batch) - summary.counters.nodes_created

                if (i + batch_size) % (batch_size * 10) == 0 or i + batch_size >= len(records):
                    progress = min(i + batch_size, len(records))
                    logger.info(f"  Progress: {progress:,}/{len(records):,} addresses ({progress * 100 // len(records)}%)")

        logger.info(f"✓ Addresses: {created:,} created, {skipped:,} already existed")

        if stats:
            stats.addresses_created = created
            stats.addresses_skipped = skipped

        return created

    except Exception as e:
        logger.error(f"✗ Address import failed: {e}")
        if stats:
            stats.errors.append(f"Address import: {e}")
        raise


# ============================================================================
# RELATIONSHIP IMPORT
# ============================================================================

# Map ICIJ relationship types to our schema
RELATIONSHIP_TYPE_MAP = {
    "officer_of": "INVOLVED_IN",
    "director of": "INVOLVED_IN",
    "shareholder of": "OWNS",
    "beneficial owner of": "OWNS",
    "beneficiary of": "OWNS",
    "nominee shareholder of": "OWNS",
    "nominee director of": "INVOLVED_IN",
    "registered_address": "HAS_ADDRESS",
    "intermediary_of": "CREATED_BY",
    "similar name and address as": "CONNECTED_TO",
    "same name and registration date as": "CONNECTED_TO",
    "same address as": "CONNECTED_TO",
    "related entity": "CONNECTED_TO",
    "underlying": "CONTROLS",
    "protector of": "CONTROLS",
    "secretary of": "INVOLVED_IN",
    "auditor of": "INVOLVED_IN",
    "power of attorney of": "INVOLVED_IN",
    "signatory of": "INVOLVED_IN",
}


async def load_relationships(
    driver: AsyncDriver,
    csv_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    stats: ImportStats = None,
) -> int:
    """
    Load relationships from ICIJ CSV.

    CSV columns expected:
        - START_ID (source node)
        - END_ID (target node)
        - TYPE (relationship type)
        - link (relationship description)
        - start_date
        - end_date
        - sourceID
    """
    logger.info(f"Loading relationships from {csv_path}...")

    if not csv_path.exists():
        logger.warning(f"⚠ Relationships file not found: {csv_path}")
        return 0

    try:
        df = pd.read_csv(csv_path, low_memory=False)
        logger.info(f"  Found {len(df):,} relationship records")

        # Normalize columns
        column_map = {
            "START_ID": "source_id",
            "END_ID": "target_id",
            "TYPE": "rel_type",
            "sourceID": "source",
        }
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

        # Map relationship types
        if "rel_type" in df.columns:
            df["mapped_type"] = df["rel_type"].str.lower().map(
                lambda x: RELATIONSHIP_TYPE_MAP.get(x, "CONNECTED_TO")
            )
        else:
            df["mapped_type"] = "CONNECTED_TO"

        date_cols = ["start_date", "end_date"]
        records = prepare_records(df, date_columns=date_cols)

        # Group by relationship type for specific queries
        # This approach handles the dynamic relationship type better

        # Generic relationship query using APOC (if available) or multiple queries
        query = """
        UNWIND $batch AS row
        
        // Find source node (could be Entity, Person, Intermediary, or Address)
        OPTIONAL MATCH (source:Entity {entity_id: row.source_id})
        WITH row, source
        OPTIONAL MATCH (source2:Person {person_id: row.source_id})
        WITH row, COALESCE(source, source2) AS source
        OPTIONAL MATCH (source3:Intermediary {intermediary_id: row.source_id})
        WITH row, COALESCE(source, source3) AS source
        OPTIONAL MATCH (source4:Address {address_id: row.source_id})
        WITH row, COALESCE(source, source4) AS source
        
        // Find target node
        OPTIONAL MATCH (target:Entity {entity_id: row.target_id})
        WITH row, source, target
        OPTIONAL MATCH (target2:Person {person_id: row.target_id})
        WITH row, source, COALESCE(target, target2) AS target
        OPTIONAL MATCH (target3:Intermediary {intermediary_id: row.target_id})
        WITH row, source, COALESCE(target, target3) AS target
        OPTIONAL MATCH (target4:Address {address_id: row.target_id})
        WITH row, source, COALESCE(target, target4) AS target
        
        // Create relationship if both nodes exist
        WHERE source IS NOT NULL AND target IS NOT NULL
        
        MERGE (source)-[r:RELATED_TO]->(target)
        ON CREATE SET
            r.relationship_type = row.rel_type,
            r.link = row.link,
            r.start_date = CASE 
                WHEN row.start_date IS NOT NULL 
                THEN date(row.start_date) 
                ELSE NULL 
            END,
            r.end_date = CASE 
                WHEN row.end_date IS NOT NULL 
                THEN date(row.end_date) 
                ELSE NULL 
            END,
            r.source = row.source,
            r.created_at = datetime()
        """

        created = 0
        skipped = 0

        async with driver.session(database=NEO4J_DATABASE) as session:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]

                try:
                    result = await session.run(query, batch=batch)
                    summary = await result.consume()
                    created += summary.counters.relationships_created
                    skipped += len(batch) - summary.counters.relationships_created

                    if (i + batch_size) % (batch_size * 5) == 0 or i + batch_size >= len(records):
                        progress = min(i + batch_size, len(records))
                        logger.info(
                            f"  Progress: {progress:,}/{len(records):,} relationships "
                            f"({progress * 100 // len(records)}%)"
                        )

                except TransientError as e:
                    logger.warning(f"  ⚠ Transient error on batch {i}: {e}")
                    await asyncio.sleep(RETRY_DELAY_SECONDS)

        logger.info(f"✓ Relationships: {created:,} created, {skipped:,} skipped (missing nodes)")

        if stats:
            stats.relationships_created = created
            stats.relationships_skipped = skipped

        return created

    except Exception as e:
        logger.error(f"✗ Relationship import failed: {e}")
        if stats:
            stats.errors.append(f"Relationship import: {e}")
        raise


# ============================================================================
# VERIFICATION QUERIES
# ============================================================================

async def verify_import(driver: AsyncDriver) -> dict:
    """
    Run verification queries to check import results.

    Returns:
        Dictionary with node and relationship counts
    """
    logger.info("Verifying import...")

    verification = {}

    queries = {
        "entities": "MATCH (e:Entity) RETURN count(e) AS count",
        "persons": "MATCH (p:Person) RETURN count(p) AS count",
        "intermediaries": "MATCH (i:Intermediary) RETURN count(i) AS count",
        "addresses": "MATCH (a:Address) RETURN count(a) AS count",
        "relationships": "MATCH ()-[r]->() RETURN count(r) AS count",
        "ownership_chains": """
            MATCH path = (p:Person)-[:RELATED_TO*1..3]->(e:Entity)
            RETURN count(DISTINCT path) AS count
            LIMIT 1
        """,
    }

    async with driver.session(database=NEO4J_DATABASE) as session:
        for name, query in queries.items():
            try:
                result = await session.run(query)
                record = await result.single()
                count = record["count"] if record else 0
                verification[name] = count
                logger.info(f"  {name}: {count:,}")
            except Exception as e:
                logger.warning(f"  ⚠ Could not verify {name}: {e}")
                verification[name] = -1

    # Sample data check
    sample_query = """
    MATCH (e:Entity)
    WHERE e.name IS NOT NULL
    RETURN e.entity_id AS id, e.name AS name, e.jurisdiction_code AS jurisdiction
    LIMIT 5
    """

    logger.info("  Sample entities:")
    async with driver.session(database=NEO4J_DATABASE) as session:
        result = await session.run(sample_query)
        records = await result.data()
        for record in records:
            logger.info(f"    - {record['id']}: {record['name']} ({record['jurisdiction']})")

    return verification


async def get_database_stats(driver: AsyncDriver) -> None:
    """Print database statistics."""
    logger.info("Database Statistics:")

    query = """
    CALL apoc.meta.stats() YIELD labels, relTypes
    RETURN labels, relTypes
    """

    try:
        async with driver.session(database=NEO4J_DATABASE) as session:
            result = await session.run(query)
            record = await result.single()

            if record:
                logger.info("  Node labels:")
                for label, count in record["labels"].items():
                    logger.info(f"    - {label}: {count:,}")

                logger.info("  Relationship types:")
                for rel_type, count in record["relTypes"].items():
                    logger.info(f"    - {rel_type}: {count:,}")
    except Exception as e:
        logger.warning(f"  ⚠ APOC not available for stats: {e}")


# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

async def run_import(
    data_dir: str = DEFAULT_DATA_DIR,
    batch_size: int = DEFAULT_BATCH_SIZE,
    skip_nodes: bool = False,
    skip_relationships: bool = False,
    verify_only: bool = False,
) -> ImportStats:
    """
    Main import orchestration function.

    Args:
        data_dir: Directory containing CSV files
        batch_size: Records per batch transaction
        skip_nodes: Skip node import (relationships only)
        skip_relationships: Skip relationship import (nodes only)
        verify_only: Only run verification, no import

    Returns:
        ImportStats object with results
    """
    stats = ImportStats()
    driver = None
    data_path = Path(data_dir)

    logger.info("=" * 60)
    logger.info("PANAMA PAPERS DATA IMPORT")
    logger.info("=" * 60)
    logger.info(f"Data directory: {data_path.absolute()}")
    logger.info(f"Batch size: {batch_size:,}")
    logger.info("")

    try:
        # Connect to database
        driver = await connect_neo4j()

        if verify_only:
            await verify_import(driver)
            await get_database_stats(driver)
            return stats

        # Import nodes
        if not skip_nodes:
            logger.info("-" * 40)
            logger.info("PHASE 1: Importing Nodes")
            logger.info("-" * 40)

            await load_entities(
                driver,
                data_path / CSV_FILES["entities"],
                batch_size,
                stats,
            )

            await load_officers(
                driver,
                data_path / CSV_FILES["officers"],
                batch_size,
                stats,
            )

            await load_intermediaries(
                driver,
                data_path / CSV_FILES["intermediaries"],
                batch_size,
                stats,
            )

            await load_addresses(
                driver,
                data_path / CSV_FILES["addresses"],
                batch_size,
                stats,
            )

        # Import relationships
        if not skip_relationships:
            logger.info("-" * 40)
            logger.info("PHASE 2: Importing Relationships")
            logger.info("-" * 40)

            await load_relationships(
                driver,
                data_path / CSV_FILES["relationships"],
                batch_size,
                stats,
            )

        # Verify import
        logger.info("-" * 40)
        logger.info("PHASE 3: Verification")
        logger.info("-" * 40)

        await verify_import(driver)

        # Print summary
        logger.info(stats.summary())

        if stats.errors:
            logger.warning("Errors encountered:")
            for error in stats.errors:
                logger.warning(f"  - {error}")

        return stats

    except Exception as e:
        logger.error(f"Import failed: {e}")
        stats.errors.append(str(e))
        raise

    finally:
        if driver:
            await close_connection(driver)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Import ICIJ Panama Papers data into Neo4j",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python seeddata.py
    python seeddata.py --data-dir ./icij-data --batch-size 5000
    python seeddata.py --verify-only
    python seeddata.py --skip-relationships

Environment variables (via .env file):
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=your_password
    NEO4J_DATABASE=neo4j
        """
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default=DEFAULT_DATA_DIR,
        help=f"Directory containing CSV files (default: {DEFAULT_DATA_DIR})"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Records per transaction batch (default: {DEFAULT_BATCH_SIZE})"
    )

    parser.add_argument(
        "--skip-nodes",
        action="store_true",
        help="Skip node import (relationships only)"
    )

    parser.add_argument(
        "--skip-relationships",
        action="store_true",
        help="Skip relationship import (nodes only)"
    )

    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only run verification queries, no import"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log file path (optional)"
    )

    args = parser.parse_args()

    # Reconfigure logging with CLI options
    global logger
    logger = setup_logging(args.log_level, args.log_file)

    # Run async import
    try:
        asyncio.run(
            run_import(
                data_dir=args.data_dir,
                batch_size=args.batch_size,
                skip_nodes=args.skip_nodes,
                skip_relationships=args.skip_relationships,
                verify_only=args.verify_only,
            )
        )
        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("Import cancelled by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()