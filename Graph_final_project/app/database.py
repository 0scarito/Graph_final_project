"""Neo4j Database Connection Manager - Singleton Pattern."""

import os
from typing import Optional, ContextManager
from contextlib import contextmanager

from neo4j import GraphDatabase, Driver, Session

from app.config import settings


class Neo4jDatabase:
    """Singleton-style Neo4j database manager."""

    _instance: Optional["Neo4jDatabase"] = None
    _driver: Optional[Driver] = None

    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(Neo4jDatabase, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the database connection."""
        if self._driver is None:
            self.connect()

    def connect(self) -> None:
        """
        Initialize the Neo4j driver using environment variables.
        
        Uses NEO4J_URI and NEO4J_PASSWORD from environment or settings.
        """
        neo4j_uri = os.getenv("NEO4J_URI") or settings.neo4j_uri
        neo4j_user = os.getenv("NEO4J_USER") or settings.neo4j_user
        neo4j_password = os.getenv("NEO4J_PASSWORD") or settings.neo4j_password

        self._driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password)
        )

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None

    @contextmanager
    def get_session(self) -> ContextManager[Session]:
        """
        Get a Neo4j session as a context manager.
        
        Usage:
            with db.get_session() as session:
                result = session.run("MATCH (n) RETURN n LIMIT 1")
        """
        if self._driver is None:
            raise RuntimeError("Database driver not initialized. Call connect() first.")
        
        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()

    def verify_connectivity(self) -> bool:
        """
        Verify connection to Neo4j database.
        
        Returns:
            True if connection is successful, raises exception otherwise
        """
        if self._driver is None:
            raise RuntimeError("Database driver not initialized. Call connect() first.")
        
        try:
            self._driver.verify_connectivity()
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to verify Neo4j connectivity: {e}")

    @property
    def driver(self) -> Optional[Driver]:
        """Get the Neo4j driver instance."""
        return self._driver


# Global database instance
db = Neo4jDatabase()


def get_database() -> Neo4jDatabase:
    """Get the global Neo4jDatabase instance."""
    return db
