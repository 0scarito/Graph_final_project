"""Graph Service - Business Logic Layer for Neo4j Queries."""

from typing import List, Dict, Any, Optional
from app.database import get_database


class GraphService:
    """
    The "Brain" of the application.
    Contains all business logic and Cypher queries for graph analysis.
    """

    def __init__(self):
        """Initialize the graph service with database connection."""
        self.db = get_database()

    def get_entity_ownership_paths(self, entity_id: str, max_depth: int = 4) -> List[Dict[str, Any]]:
        """
        Trace how an Officer is connected to a specific Entity.
        Uses variable-length paths to find ownership chains.

        Args:
            entity_id: The ID of the target entity
            max_depth: Maximum path depth to search (default: 4)

        Returns:
            List of paths, each containing nodes and relationships as JSON-friendly structures
        """
        query = """
        MATCH p = (o:Officer)-[:OFFICER_OF*1..$max_depth]->(e:Entity {id: $entity_id})
        RETURN p
        ORDER BY length(p)
        LIMIT 100
        """

        paths = []
        with self.db.get_session() as session:
            result = session.run(query, entity_id=entity_id, max_depth=max_depth)
            
            for record in result:
                path = record["p"]
                
                # Extract nodes
                nodes = []
                for node in path.nodes:
                    nodes.append({
                        "id": node.get("id", str(node.id)),
                        "labels": list(node.labels),
                        "properties": dict(node)
                    })
                
                # Extract relationships
                relationships = []
                for rel in path.relationships:
                    relationships.append({
                        "type": rel.type,
                        "start_node": str(rel.start_node.get("id", rel.start_node.id)),
                        "end_node": str(rel.end_node.get("id", rel.end_node.id)),
                        "properties": dict(rel)
                    })
                
                paths.append({
                    "nodes": nodes,
                    "relationships": relationships,
                    "length": len(path.relationships)
                })

        return paths

    def get_top_intermediaries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Find "Hubs" - intermediaries that manage many entities.
        These are key players in the offshore network.

        Args:
            limit: Maximum number of results to return (default: 20)

        Returns:
            List of intermediaries with their entity counts, sorted by count descending
        """
        query = """
        MATCH (i:Intermediary)-[:INTERMEDIARY_OF]->(e:Entity)
        WITH i, count(e) as entity_count
        ORDER BY entity_count DESC
        LIMIT $limit
        RETURN i.id as intermediary_id,
               i.name as name,
               entity_count
        """

        intermediaries = []
        with self.db.get_session() as session:
            result = session.run(query, limit=limit)
            
            for record in result:
                intermediaries.append({
                    "intermediary_id": record["intermediary_id"],
                    "name": record["name"],
                    "entity_count": record["entity_count"]
                })

        return intermediaries

    def detect_red_flags(self, min_entities: int = 10, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Find suspicious clusters - many entities registered at the exact same address.
        This is a red flag for potential shell company rings.

        Args:
            min_entities: Minimum number of entities sharing an address to flag (default: 10)
            limit: Maximum number of results to return (default: 50)

        Returns:
            List of suspicious addresses with entity counts and sample entities
        """
        query = """
        MATCH (a:Address)<-[:REGISTERED_ADDRESS]-(e:Entity)
        WITH a, count(e) as count, collect(e.name) as entities
        WHERE count > $min_entities
        RETURN a.id as address_id,
               a.address as address,
               count,
               entities[0..5] as sample_entities
        ORDER BY count DESC
        LIMIT $limit
        """

        red_flags = []
        with self.db.get_session() as session:
            result = session.run(query, min_entities=min_entities, limit=limit)
            
            for record in result:
                red_flags.append({
                    "address_id": record["address_id"],
                    "address": record["address"],
                    "entity_count": record["count"],
                    "sample_entities": record["sample_entities"]
                })

        return red_flags

    def get_entity_details(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Simple lookup for an Entity.
        Returns the Entity properties plus the name of its Jurisdiction.

        Args:
            entity_id: The ID of the entity to lookup

        Returns:
            Dictionary with entity details and jurisdiction name, or None if not found
        """
        query = """
        MATCH (e:Entity {id: $entity_id})
        OPTIONAL MATCH (e)-[:REGISTERED_IN]->(j:Jurisdiction)
        RETURN e,
               j.name as jurisdiction_name
        LIMIT 1
        """

        with self.db.get_session() as session:
            result = session.run(query, entity_id=entity_id)
            record = result.single()
            
            if record is None:
                return None
            
            entity = record["e"]
            return {
                "id": entity.get("id", str(entity.id)),
                "name": entity.get("name"),
                "source": entity.get("source"),
                "node_type": entity.get("node_type"),
                "jurisdiction_name": record["jurisdiction_name"],
                "properties": dict(entity)
            }

    def get_shortest_path(self, start_node_id: str, end_node_id: str) -> Optional[Dict[str, Any]]:
        """
        Find the shortest path between two nodes using Neo4j's shortestPath function.
        
        Args:
            start_node_id: The ID of the starting node
            end_node_id: The ID of the ending node
            
        Returns:
            Dictionary containing the path with nodes and relationships, or None if no path exists
        """
        query = """
        MATCH p = shortestPath((a)-[*]-(b))
        WHERE a.id = $start_id AND b.id = $end_id
        RETURN p
        LIMIT 1
        """
        
        with self.db.get_session() as session:
            result = session.run(query, start_id=start_node_id, end_id=end_node_id)
            record = result.single()
            
            if record is None:
                return None
            
            path = record["p"]
            
            # Extract nodes
            nodes = []
            for node in path.nodes:
                nodes.append({
                    "id": node.get("id", str(node.id)),
                    "labels": list(node.labels),
                    "properties": dict(node)
                })
            
            # Extract relationships
            relationships = []
            for rel in path.relationships:
                relationships.append({
                    "type": rel.type,
                    "start_node": str(rel.start_node.get("id", rel.start_node.id)),
                    "end_node": str(rel.end_node.get("id", rel.end_node.id)),
                    "properties": dict(rel)
                })
            
            return {
                "nodes": nodes,
                "relationships": relationships,
                "length": len(path.relationships)
            }

    def get_most_connected_officers(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Find the most connected officers using centrality analysis.
        Officers are ranked by their degree (number of entities they are connected to).
        
        Args:
            limit: Maximum number of results to return (default: 20)
            
        Returns:
            List of officers with their connection counts (degree), sorted by degree descending
        """
        query = """
        MATCH (o:Officer)-[:OFFICER_OF]->(e:Entity)
        WITH o, count(e) as degree
        ORDER BY degree DESC
        LIMIT $limit
        RETURN o.id as officer_id,
               o.name as name,
               degree
        """
        
        officers = []
        with self.db.get_session() as session:
            result = session.run(query, limit=limit)
            
            for record in result:
                officers.append({
                    "officer_id": record["officer_id"],
                    "name": record["name"],
                    "degree": record["degree"]
                })
        
        return officers
