"""
Panama Papers API - Entity Routes
==================================

FastAPI router for entity-related endpoints.

Endpoints:
    GET /entities/{entity_id}           - Get entity by ID
    GET /entities/search                - Search entities by name
    GET /entities/{entity_id}/ownership - Get ownership chain
    GET /entities/{entity_id}/network   - Get connected entities
    GET /entities/top/influential       - Get top entities by PageRank
    GET /entities/top/connected         - Get most connected entities
    GET /entities/by-jurisdiction       - Get entities by jurisdiction
    GET /entities/{entity_id}/risk      - Get entity risk analysis

All queries include LIMIT clauses to prevent Cartesian products.
All responses use Pydantic models for validation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from neo4j import AsyncSession
from neo4j.exceptions import Neo4jError

# Import models (adjust path based on your project structure)
from app.models import (
    EntityResponse,
    EntitySummary,
    EntityType,
    EntityStatus,
    PathQuery,
    PathResponse,
    PathResult,
    PathNode,
    PathEdge,
    RelationshipResponse,
    RelationshipType,
    RiskLevel,
    RedFlagAnalysis,
    RedFlag,
    SearchQuery,
    SearchResponse,
    SearchResult,
    InfluenceScore,
    ErrorResponse,
    PaginationMeta,
)

# Import database utilities (adjust path based on your project structure)
from app.database import get_db_session, run_query, run_query_single

# ============================================================================
# CONFIGURATION
# ============================================================================

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(
    prefix="/entities",
    tags=["entities"],
    responses={
        404: {"model": ErrorResponse, "description": "Entity not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_entity_record(record: dict[str, Any], prefix: str = "e") -> EntityResponse:
    """
    Parse a Neo4j entity record into an EntityResponse.
    
    Args:
        record: Neo4j record dictionary
        prefix: Key prefix for entity properties (default: "e")
    
    Returns:
        EntityResponse model instance
    """
    entity = record.get(prefix, record)
    
    # Handle both direct properties and nested dict
    if isinstance(entity, dict):
        data = entity
    else:
        # Neo4j Node object
        data = dict(entity)
    
    return EntityResponse(
        entity_id=data.get("entity_id", ""),
        name=data.get("name", "Unknown"),
        jurisdiction_code=data.get("jurisdiction_code") or data.get("jurisdiction"),
        entity_type=data.get("entity_type") or data.get("type") or EntityType.UNKNOWN,
        status=data.get("status") or EntityStatus.UNKNOWN,
        pagerank_score=data.get("pagerank_score"),
        community_id=data.get("community_id"),
        degree_centrality=data.get("degree_centrality"),
        betweenness_score=data.get("betweenness_score"),
        risk_score=data.get("risk_score"),
        risk_level=data.get("risk_level"),
        incorporation_date=data.get("incorporation_date"),
        inactivation_date=data.get("inactivation_date"),
        source=data.get("source"),
    )


def calculate_effective_ownership(percentages: list[Optional[float]]) -> Optional[float]:
    """
    Calculate effective ownership through a chain.
    
    Multiplies ownership percentages through the chain.
    Example: 50% -> 50% -> 50% = 12.5% effective ownership
    """
    if not percentages:
        return None
    
    result = 100.0
    for pct in percentages:
        if pct is not None:
            result = result * pct / 100.0
    
    return round(result, 4)


# ============================================================================
# ENDPOINT 1: GET ENTITY BY ID
# ============================================================================

@router.get(
    "/id/{entity_id}",
    response_model=EntityResponse,
    summary="Get entity by ID",
    responses={
        200: {"description": "Entity found"},
        404: {"description": "Entity not found"},
    },
)
async def get_entity(
    entity_id: Annotated[
        str,
        Path(
            description="Unique entity identifier",
            min_length=1,
            max_length=50,
            examples=["10000001", "ENT-BVI-2010-001"],
        ),
    ],
    include_analytics: Annotated[
        bool,
        Query(description="Include PageRank and community data"),
    ] = True,
    include_counts: Annotated[
        bool,
        Query(description="Include owner/subsidiary counts"),
    ] = False,
    session: AsyncSession = Depends(get_db_session),
) -> EntityResponse:
    """
    Retrieve detailed information about a specific entity.
    
    Returns entity properties including:
    - Basic info: name, jurisdiction, type, status
    - Analytics: PageRank score, community ID (if include_analytics=True)
    - Counts: owner/subsidiary counts (if include_counts=True)
    
    Args:
        entity_id: Unique entity identifier
        include_analytics: Include GDS algorithm results
        include_counts: Include relationship counts
        session: Neo4j session (injected)
    
    Returns:
        EntityResponse with full entity details
    
    Raises:
        HTTPException 404: Entity not found
        HTTPException 500: Database error
    """
    # Build query based on options
    if include_counts:
        query = """
        MATCH (e:Entity {entity_id: $entity_id})
        OPTIONAL MATCH (owner)-[:OWNS]->(e)
        OPTIONAL MATCH (e)-[:OWNS]->(subsidiary)
        WITH e, 
             count(DISTINCT owner) AS owner_count,
             count(DISTINCT subsidiary) AS subsidiary_count
        RETURN e {
            .*,
            owner_count: owner_count,
            subsidiary_count: subsidiary_count
        } AS entity
        LIMIT 1
        """
    else:
        query = """
        MATCH (e:Entity {entity_id: $entity_id})
        RETURN e AS entity
        LIMIT 1
        """
    
    try:
        result = await session.run(query, {"entity_id": entity_id})
        record = await result.single()
        
        if not record:
            logger.info(f"Entity not found: {entity_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity with ID '{entity_id}' not found",
            )
        
        entity_data = record["entity"]
        
        # Build response
        response = EntityResponse(
            entity_id=entity_data.get("entity_id", entity_id),
            name=entity_data.get("name", "Unknown"),
            jurisdiction_code=entity_data.get("jurisdiction_code") or entity_data.get("jurisdiction"),
            entity_type=entity_data.get("entity_type") or entity_data.get("type") or EntityType.UNKNOWN,
            status=entity_data.get("status") or EntityStatus.UNKNOWN,
            incorporation_date=entity_data.get("incorporation_date"),
            inactivation_date=entity_data.get("inactivation_date"),
            source=entity_data.get("source"),
        )
        
        # Add analytics if requested
        if include_analytics:
            response.pagerank_score = entity_data.get("pagerank_score")
            response.community_id = entity_data.get("community_id")
            response.degree_centrality = entity_data.get("degree_centrality")
            response.betweenness_score = entity_data.get("betweenness_score")
        
        # Add counts if requested
        if include_counts:
            response.owner_count = entity_data.get("owner_count", 0)
            response.subsidiary_count = entity_data.get("subsidiary_count", 0)
        
        return response
        
    except HTTPException:
        raise
    except Neo4jError as e:
        logger.error(f"Neo4j error fetching entity {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed",
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching entity {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


# ============================================================================
# ENDPOINT 2: SEARCH ENTITIES
# ============================================================================

@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search entities by name",
)
async def search_entities(
    q: Annotated[
        str,
        Query(
            description="Search query (entity name)",
            min_length=2,
            max_length=200,
            examples=["Holdings", "Acme", "Global Ventures"],
        ),
    ],
    jurisdiction: Annotated[
        Optional[str],
        Query(description="Filter by jurisdiction code"),
    ] = None,
    entity_type: Annotated[
        Optional[EntityType],
        Query(description="Filter by entity type"),
    ] = None,
    status_filter: Annotated[
        Optional[EntityStatus],
        Query(alias="status", description="Filter by status"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum results"),
    ] = 20,
    offset: Annotated[
        int,
        Query(ge=0, description="Pagination offset"),
    ] = 0,
    use_fulltext: Annotated[
        bool,
        Query(description="Use full-text search index"),
    ] = True,
    session: AsyncSession = Depends(get_db_session),
) -> SearchResponse:
    """
    Search entities by name with optional filters.
    
    Supports two search modes:
    - Full-text search (default): Uses Neo4j full-text index for fuzzy matching
    - Contains search: Simple CONTAINS matching (case-insensitive)
    
    Args:
        q: Search query string
        jurisdiction: Filter by jurisdiction code (e.g., "BVI", "PAN")
        entity_type: Filter by entity type
        status_filter: Filter by entity status
        limit: Maximum number of results (1-100)
        offset: Pagination offset
        use_fulltext: Use full-text index (faster, fuzzy matching)
        session: Neo4j session (injected)
    
    Returns:
        SearchResponse with matching entities and pagination info
    """
    import time
    start_time = time.perf_counter()
    
    params: dict[str, Any] = {
        "query": q,
        "limit": limit,
        "offset": offset,
    }
    
    # Build filter conditions
    filters = []
    if jurisdiction:
        filters.append("e.jurisdiction_code = $jurisdiction")
        params["jurisdiction"] = jurisdiction.upper()
    if entity_type:
        filters.append("e.entity_type = $entity_type")
        params["entity_type"] = entity_type.value
    if status_filter:
        filters.append("e.status = $status")
        params["status"] = status_filter.value
    
    filter_clause = " AND " + " AND ".join(filters) if filters else ""
    
    if use_fulltext:
        # Use full-text index for better performance and fuzzy matching
        query = f"""
        CALL db.index.fulltext.queryNodes('entity_name_fulltext', $query)
        YIELD node AS e, score
        WHERE e:Entity{filter_clause}
        WITH e, score
        ORDER BY score DESC
        SKIP $offset
        LIMIT $limit
        RETURN e, score
        """
        
        count_query = f"""
        CALL db.index.fulltext.queryNodes('entity_name_fulltext', $query)
        YIELD node AS e, score
        WHERE e:Entity{filter_clause}
        RETURN count(e) AS total
        """
    else:
        # Fallback to CONTAINS search
        query = f"""
        MATCH (e:Entity)
        WHERE toLower(e.name) CONTAINS toLower($query){filter_clause}
        WITH e
        ORDER BY e.name
        SKIP $offset
        LIMIT $limit
        RETURN e, 1.0 AS score
        """
        
        count_query = f"""
        MATCH (e:Entity)
        WHERE toLower(e.name) CONTAINS toLower($query){filter_clause}
        RETURN count(e) AS total
        """
    
    try:
        # Execute search query
        result = await session.run(query, params)
        records = await result.fetch(limit)
        
        # Get total count for pagination
        count_result = await session.run(count_query, params)
        count_record = await count_result.single()
        total = count_record["total"] if count_record else 0
        
        # Build response
        search_results = []
        for record in records:
            entity = record["e"]
            score = record.get("score", 1.0)
            
            search_results.append(
                SearchResult(
                    node_id=entity.get("entity_id", ""),
                    name=entity.get("name", "Unknown"),
                    node_type="Entity",
                    relevance_score=min(score / 10.0, 1.0) if score > 1 else score,
                    jurisdiction_code=entity.get("jurisdiction_code"),
                    status=entity.get("status"),
                    risk_level=entity.get("risk_level"),
                    matched_field="name",
                )
            )
        
        execution_time = (time.perf_counter() - start_time) * 1000
        
        return SearchResponse(
            query=q,
            total_results=total,
            results=search_results,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
            execution_time_ms=round(execution_time, 2),
        )
        
    except Neo4jError as e:
        # Check if full-text index doesn't exist
        if "index" in str(e).lower() and use_fulltext:
            logger.warning(f"Full-text index not found, falling back to CONTAINS: {e}")
            # Retry without full-text
            return await search_entities(
                q=q,
                jurisdiction=jurisdiction,
                entity_type=entity_type,
                status_filter=status_filter,
                limit=limit,
                offset=offset,
                use_fulltext=False,
                session=session,
            )
        
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search query failed",
        )
    except Exception as e:
        logger.error(f"Unexpected search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during search",
        )


# ============================================================================
# ENDPOINT 3: OWNERSHIP PATH
# ============================================================================

@router.get(
    "/id/{entity_id}/ownership-path",
    response_model=PathResponse,
    summary="Get beneficial ownership chain",
)
async def get_ownership_path(
    entity_id: Annotated[
        str,
        Path(description="Target entity identifier"),
    ],
    max_depth: Annotated[
        int,
        Query(ge=1, le=6, description="Maximum path depth (hops)"),
    ] = 4,
    min_depth: Annotated[
        int,
        Query(ge=1, le=6, description="Minimum path depth"),
    ] = 1,
    include_persons: Annotated[
        bool,
        Query(description="Include Person nodes as beneficial owners"),
    ] = True,
    only_active: Annotated[
        bool,
        Query(description="Only include active ownership relationships"),
    ] = True,
    limit: Annotated[
        int,
        Query(ge=1, le=50, description="Maximum paths to return"),
    ] = 20,
    session: AsyncSession = Depends(get_db_session),
) -> PathResponse:
    """
    Trace beneficial ownership chain for an entity.
    
    Finds all ownership paths from beneficial owners (Person nodes)
    to the target entity through OWNS relationships.
    
    Returns:
    - All paths found within depth limits
    - Effective ownership percentages calculated through chains
    - Risk indicators (PEPs, tax havens, deep layering)
    
    Args:
        entity_id: Target entity to trace ownership for
        max_depth: Maximum number of hops (1-6)
        min_depth: Minimum number of hops
        include_persons: Include Person nodes at path ends
        only_active: Only active ownership relationships
        limit: Maximum number of paths to return
        session: Neo4j session (injected)
    
    Returns:
        PathResponse with ownership paths and analysis
    
    Raises:
        HTTPException 404: Entity not found or no paths found
    """
    import time
    start_time = time.perf_counter()
    
    # First verify entity exists
    verify_query = """
    MATCH (e:Entity {entity_id: $entity_id})
    RETURN e.name AS name
    LIMIT 1
    """
    
    try:
        verify_result = await session.run(verify_query, {"entity_id": entity_id})
        verify_record = await verify_result.single()
        
        if not verify_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity '{entity_id}' not found",
            )
        
        # Build ownership path query
        owner_label = "Person|Entity" if include_persons else "Entity"
        status_filter = "AND ALL(r IN relationships(path) WHERE r.status = 'Active')" if only_active else ""
        
        query = f"""
        MATCH path = (owner:{owner_label})-[:OWNS*{min_depth}..{max_depth}]->(target:Entity {{entity_id: $entity_id}})
        WHERE owner <> target
        {status_filter}
        WITH path,
             nodes(path) AS path_nodes,
             relationships(path) AS path_rels,
             length(path) AS depth
        ORDER BY depth ASC
        LIMIT $limit
        RETURN 
            [n IN path_nodes | {{
                id: COALESCE(n.entity_id, n.person_id),
                name: COALESCE(n.name, n.full_name),
                type: labels(n)[0],
                jurisdiction: n.jurisdiction_code,
                is_pep: n.is_pep
            }}] AS nodes,
            [r IN path_rels | {{
                source: COALESCE(startNode(r).entity_id, startNode(r).person_id),
                target: COALESCE(endNode(r).entity_id, endNode(r).person_id),
                type: type(r),
                percentage: r.ownership_percentage,
                is_nominee: r.is_nominee
            }}] AS relationships,
            depth
        """
        
        result = await session.run(query, {"entity_id": entity_id, "limit": limit})
        records = await result.fetch(limit)
        
        if not records:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No ownership paths found for entity '{entity_id}'",
            )
        
        # Process paths
        paths: list[PathResult] = []
        all_entity_ids: set[str] = set()
        all_person_ids: set[str] = set()
        pep_count = 0
        tax_haven_jurisdictions: set[str] = set()
        
        # Known tax havens for risk analysis
        TAX_HAVENS = {"BVI", "PAN", "CYM", "JEY", "GGY", "IMN", "BMU", "VGB", "LIE", "MCO"}
        
        for idx, record in enumerate(records):
            nodes_data = record["nodes"]
            rels_data = record["relationships"]
            depth = record["depth"]
            
            # Build path nodes
            path_nodes: list[PathNode] = []
            for layer, node in enumerate(nodes_data):
                node_id = node["id"]
                node_type = node["type"]
                
                if node_type == "Person":
                    all_person_ids.add(node_id)
                    if node.get("is_pep"):
                        pep_count += 1
                else:
                    all_entity_ids.add(node_id)
                
                jurisdiction = node.get("jurisdiction")
                if jurisdiction and jurisdiction in TAX_HAVENS:
                    tax_haven_jurisdictions.add(jurisdiction)
                
                path_nodes.append(PathNode(
                    node_id=node_id,
                    name=node["name"],
                    node_type=node_type,
                    jurisdiction_code=jurisdiction,
                    layer=layer,
                    is_pep=node.get("is_pep"),
                ))
            
            # Build path edges
            path_edges: list[PathEdge] = []
            ownership_percentages: list[Optional[float]] = []
            
            for layer, rel in enumerate(rels_data):
                pct = rel.get("percentage")
                ownership_percentages.append(pct)
                
                path_edges.append(PathEdge(
                    source_id=rel["source"],
                    target_id=rel["target"],
                    relationship_type=rel["type"],
                    ownership_percentage=pct,
                    layer=layer,
                ))
            
            # Calculate effective ownership
            effective_ownership = calculate_effective_ownership(ownership_percentages)
            
            # Identify risk indicators
            risk_indicators = []
            if depth >= 4:
                risk_indicators.append("DEEP_LAYERING")
            if any(n.get("is_pep") for n in nodes_data):
                risk_indicators.append("PEP_CONNECTION")
            if any(rel.get("is_nominee") for rel in rels_data):
                risk_indicators.append("NOMINEE_ARRANGEMENT")
            if len(tax_haven_jurisdictions) >= 2:
                risk_indicators.append("MULTI_JURISDICTION")
            
            paths.append(PathResult(
                path_id=idx + 1,
                depth=depth,
                nodes=path_nodes,
                edges=path_edges,
                effective_ownership=effective_ownership,
                risk_indicators=risk_indicators,
            ))
        
        # Calculate summary statistics
        depths = [p.depth for p in paths]
        avg_depth = sum(depths) / len(depths) if depths else 0
        
        execution_time = (time.perf_counter() - start_time) * 1000
        
        # Build query object for response
        query_obj = PathQuery(
            source_entity_id=entity_id,
            max_depth=max_depth,
            min_depth=min_depth,
            include_persons=include_persons,
            only_active=only_active,
            limit=limit,
        )
        
        return PathResponse(
            query=query_obj,
            path_count=len(paths),
            paths=paths,
            average_depth=round(avg_depth, 2),
            max_depth_found=max(depths) if depths else 0,
            unique_entities=len(all_entity_ids),
            unique_persons=len(all_person_ids),
            pep_count=pep_count,
            tax_haven_count=len(tax_haven_jurisdictions),
            execution_time_ms=round(execution_time, 2),
        )
        
    except HTTPException:
        raise
    except Neo4jError as e:
        logger.error(f"Neo4j error in ownership path query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ownership path query failed",
        )
    except Exception as e:
        logger.error(f"Unexpected error in ownership path: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


# ============================================================================
# ENDPOINT 4: ENTITY NETWORK
# ============================================================================

@router.get(
    "/id/{entity_id}/network",
    response_model=list[RelationshipResponse],
    summary="Get connected entities (network neighbors)",
)
async def get_entity_network(
    entity_id: Annotated[
        str,
        Path(description="Entity identifier"),
    ],
    depth: Annotated[
        int,
        Query(ge=1, le=3, description="Network depth (1-3 hops)"),
    ] = 1,
    direction: Annotated[
        str,
        Query(description="Relationship direction: in, out, or both"),
    ] = "both",
    relationship_types: Annotated[
        Optional[str],
        Query(description="Comma-separated relationship types to include"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum connections to return"),
    ] = 50,
    session: AsyncSession = Depends(get_db_session),
) -> list[RelationshipResponse]:
    """
    Get entities connected to the target entity.
    
    Returns direct neighbors and their relationship metadata.
    
    Args:
        entity_id: Target entity identifier
        depth: How many hops to traverse (1-3)
        direction: Relationship direction (in, out, both)
        relationship_types: Filter by relationship types
        limit: Maximum results
        session: Neo4j session (injected)
    
    Returns:
        List of relationships with connected entity details
    """
    # Parse relationship types
    rel_types = ["OWNS", "CONTROLS", "INVOLVED_IN", "CONNECTED_TO"]
    if relationship_types:
        rel_types = [rt.strip().upper() for rt in relationship_types.split(",")]
    
    rel_pattern = "|".join(rel_types)
    
    # Build direction pattern
    if direction == "in":
        pattern = f"<-[r:{rel_pattern}*1..{depth}]-"
    elif direction == "out":
        pattern = f"-[r:{rel_pattern}*1..{depth}]->"
    else:
        pattern = f"-[r:{rel_pattern}*1..{depth}]-"
    
    query = f"""
    MATCH (e:Entity {{entity_id: $entity_id}}){pattern}(n)
    WHERE e <> n
    WITH DISTINCT n, r[0] AS rel, e
    RETURN 
        COALESCE(n.entity_id, n.person_id, n.intermediary_id) AS target_id,
        COALESCE(n.name, n.full_name) AS target_name,
        labels(n)[0] AS target_type,
        n.jurisdiction_code AS target_jurisdiction,
        type(rel) AS relationship_type,
        rel.ownership_percentage AS ownership_percentage,
        rel.role AS role,
        rel.is_nominee AS is_nominee,
        rel.status AS status,
        CASE 
            WHEN startNode(rel) = e THEN 'outgoing'
            ELSE 'incoming'
        END AS direction
    ORDER BY relationship_type, target_name
    LIMIT $limit
    """
    
    try:
        result = await session.run(query, {"entity_id": entity_id, "limit": limit})
        records = await result.fetch(limit)
        
        if not records:
            # Check if entity exists
            verify = await session.run(
                "MATCH (e:Entity {entity_id: $id}) RETURN e LIMIT 1",
                {"id": entity_id}
            )
            if not await verify.single():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Entity '{entity_id}' not found",
                )
            # Entity exists but has no connections
            return []
        
        relationships = []
        for record in records:
            # Determine source/target based on direction
            if record["direction"] == "outgoing":
                source_id = entity_id
                target_id = record["target_id"]
            else:
                source_id = record["target_id"]
                target_id = entity_id
            
            relationships.append(RelationshipResponse(
                source_id=source_id,
                target_id=target_id,
                relationship_type=RelationshipType(record["relationship_type"]) 
                    if record["relationship_type"] in RelationshipType.__members__.values() 
                    else RelationshipType.CONNECTED_TO,
                target_name=record["target_name"],
                target_type=record["target_type"],
                ownership_percentage=record.get("ownership_percentage"),
                role=record.get("role"),
                is_nominee=record.get("is_nominee"),
                status=record.get("status"),
            ))
        
        return relationships
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Network query error for {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Network query failed",
        )


# ============================================================================
# ENDPOINT 5: TOP INFLUENTIAL ENTITIES
# ============================================================================

@router.get(
    "/top/influential",
    response_model=list[InfluenceScore],
    summary="Get most influential entities by PageRank",
)
async def get_influential_entities(
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Number of results"),
    ] = 20,
    jurisdiction: Annotated[
        Optional[str],
        Query(description="Filter by jurisdiction"),
    ] = None,
    entity_type: Annotated[
        Optional[EntityType],
        Query(description="Filter by entity type"),
    ] = None,
    min_score: Annotated[
        Optional[float],
        Query(ge=0, description="Minimum PageRank score"),
    ] = None,
    session: AsyncSession = Depends(get_db_session),
) -> list[InfluenceScore]:
    """
    Get the most influential entities ranked by PageRank score.
    
    PageRank measures influence based on ownership network structure.
    Higher scores indicate entities that are owned by other important entities.
    
    Args:
        limit: Number of results (1-100)
        jurisdiction: Filter by jurisdiction code
        entity_type: Filter by entity type
        min_score: Minimum PageRank score threshold
        session: Neo4j session (injected)
    
    Returns:
        List of entities ranked by influence score
    """
    # Build filters
    filters = ["e.pagerank_score IS NOT NULL"]
    params: dict[str, Any] = {"limit": limit}
    
    if jurisdiction:
        filters.append("e.jurisdiction_code = $jurisdiction")
        params["jurisdiction"] = jurisdiction.upper()
    
    if entity_type:
        filters.append("e.entity_type = $entity_type")
        params["entity_type"] = entity_type.value
    
    if min_score is not None:
        filters.append("e.pagerank_score >= $min_score")
        params["min_score"] = min_score
    
    filter_clause = " AND ".join(filters)
    
    query = f"""
    MATCH (e:Entity)
    WHERE {filter_clause}
    OPTIONAL MATCH (e)-[:REGISTERED_IN]->(j:Jurisdiction)
    WITH e, j
    ORDER BY e.pagerank_score DESC
    LIMIT $limit
    WITH e, j, 
         row_number() OVER () AS rank
    RETURN 
        e.entity_id AS entity_id,
        e.name AS name,
        e.entity_type AS entity_type,
        e.jurisdiction_code AS jurisdiction_code,
        e.pagerank_score AS pagerank_score,
        e.degree_centrality AS degree_centrality,
        e.betweenness_score AS betweenness_score,
        e.community_id AS community_id,
        j.is_tax_haven AS is_tax_haven,
        rank
    """
    
    try:
        result = await session.run(query, params)
        records = await result.fetch(limit)
        
        # Calculate percentile based on rank
        total = len(records)
        
        influence_scores = []
        for record in records:
            rank = record["rank"]
            percentile = ((total - rank + 1) / total) * 100 if total > 0 else 0
            
            influence_scores.append(InfluenceScore(
                entity_id=record["entity_id"],
                name=record["name"],
                entity_type=record.get("entity_type"),
                jurisdiction_code=record.get("jurisdiction_code"),
                pagerank_score=record["pagerank_score"],
                rank=rank,
                percentile=round(percentile, 2),
                degree_centrality=record.get("degree_centrality"),
                betweenness_score=record.get("betweenness_score"),
                community_id=record.get("community_id"),
                is_tax_haven=record.get("is_tax_haven"),
            ))
        
        return influence_scores
        
    except Exception as e:
        logger.error(f"Influential entities query error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query failed",
        )


# ============================================================================
# ENDPOINT 6: TOP CONNECTED ENTITIES
# ============================================================================

@router.get(
    "/top/connected",
    response_model=list[InfluenceScore],
    summary="Get most connected entities by degree centrality",
)
async def get_most_connected_entities(
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Number of results"),
    ] = 20,
    jurisdiction: Annotated[
        Optional[str],
        Query(description="Filter by jurisdiction"),
    ] = None,
    session: AsyncSession = Depends(get_db_session),
) -> list[InfluenceScore]:
    """
    Get entities with the most connections (highest degree centrality).
    
    Degree centrality counts direct ownership and control relationships.
    High values indicate hub entities in the network.
    
    Args:
        limit: Number of results
        jurisdiction: Filter by jurisdiction
        session: Neo4j session (injected)
    
    Returns:
        List of most connected entities
    """
    filters = ["e.degree_centrality IS NOT NULL"]
    params: dict[str, Any] = {"limit": limit}
    
    if jurisdiction:
        filters.append("e.jurisdiction_code = $jurisdiction")
        params["jurisdiction"] = jurisdiction.upper()
    
    filter_clause = " AND ".join(filters)
    
    query = f"""
    MATCH (e:Entity)
    WHERE {filter_clause}
    WITH e
    ORDER BY e.degree_centrality DESC
    LIMIT $limit
    WITH e, row_number() OVER () AS rank
    RETURN 
        e.entity_id AS entity_id,
        e.name AS name,
        e.entity_type AS entity_type,
        e.jurisdiction_code AS jurisdiction_code,
        e.pagerank_score AS pagerank_score,
        e.degree_centrality AS degree_centrality,
        e.community_id AS community_id,
        rank
    """
    
    try:
        result = await session.run(query, params)
        records = await result.fetch(limit)
        
        return [
            InfluenceScore(
                entity_id=r["entity_id"],
                name=r["name"],
                entity_type=r.get("entity_type"),
                jurisdiction_code=r.get("jurisdiction_code"),
                pagerank_score=r.get("pagerank_score") or 0,
                rank=r["rank"],
                degree_centrality=r.get("degree_centrality"),
                community_id=r.get("community_id"),
            )
            for r in records
        ]
        
    except Exception as e:
        logger.error(f"Connected entities query error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query failed",
        )


# ============================================================================
# ENDPOINT 7: ENTITIES BY JURISDICTION
# ============================================================================

@router.get(
    "/by-jurisdiction/{jurisdiction_code}",
    response_model=list[EntitySummary],
    summary="Get entities by jurisdiction",
)
async def get_entities_by_jurisdiction(
    jurisdiction_code: Annotated[
        str,
        Path(description="Jurisdiction code (e.g., BVI, PAN)"),
    ],
    status_filter: Annotated[
        Optional[EntityStatus],
        Query(alias="status", description="Filter by status"),
    ] = None,
    entity_type: Annotated[
        Optional[EntityType],
        Query(description="Filter by entity type"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=500, description="Maximum results"),
    ] = 100,
    offset: Annotated[
        int,
        Query(ge=0, description="Pagination offset"),
    ] = 0,
    session: AsyncSession = Depends(get_db_session),
) -> list[EntitySummary]:
    """
    Get all entities registered in a specific jurisdiction.
    
    Args:
        jurisdiction_code: Jurisdiction code (e.g., BVI, PAN, CYM)
        status_filter: Filter by entity status
        entity_type: Filter by entity type
        limit: Maximum results
        offset: Pagination offset
        session: Neo4j session (injected)
    
    Returns:
        List of entity summaries
    """
    filters = ["e.jurisdiction_code = $jurisdiction"]
    params: dict[str, Any] = {
        "jurisdiction": jurisdiction_code.upper(),
        "limit": limit,
        "offset": offset,
    }
    
    if status_filter:
        filters.append("e.status = $status")
        params["status"] = status_filter.value
    
    if entity_type:
        filters.append("e.entity_type = $entity_type")
        params["entity_type"] = entity_type.value
    
    filter_clause = " AND ".join(filters)
    
    query = f"""
    MATCH (e:Entity)
    WHERE {filter_clause}
    WITH e
    ORDER BY e.name
    SKIP $offset
    LIMIT $limit
    RETURN 
        e.entity_id AS entity_id,
        e.name AS name,
        e.jurisdiction_code AS jurisdiction_code,
        e.entity_type AS entity_type,
        e.status AS status,
        e.risk_level AS risk_level
    """
    
    try:
        result = await session.run(query, params)
        records = await result.fetch(limit)
        
        return [
            EntitySummary(
                entity_id=r["entity_id"],
                name=r["name"],
                jurisdiction_code=r.get("jurisdiction_code"),
                entity_type=r.get("entity_type"),
                status=r.get("status"),
                risk_level=r.get("risk_level"),
            )
            for r in records
        ]
        
    except Exception as e:
        logger.error(f"Jurisdiction query error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query failed",
        )


# ============================================================================
# ENDPOINT 8: ENTITY RISK ANALYSIS
# ============================================================================

@router.get(
    "/id/{entity_id}/risk",
    response_model=RedFlagAnalysis,
    summary="Get entity risk analysis",
)
async def get_entity_risk_analysis(
    entity_id: Annotated[
        str,
        Path(description="Entity identifier"),
    ],
    session: AsyncSession = Depends(get_db_session),
) -> RedFlagAnalysis:
    """
    Perform risk analysis on an entity.
    
    Analyzes:
    - Ownership depth (layering)
    - Jurisdiction risk
    - PEP connections
    - Circular ownership patterns
    - Mass registration addresses
    
    Args:
        entity_id: Entity to analyze
        session: Neo4j session (injected)
    
    Returns:
        RedFlagAnalysis with risk score and identified flags
    """
    # Multi-part query for risk analysis
    query = """
    // Get entity details
    MATCH (e:Entity {entity_id: $entity_id})
    
    // Check ownership depth
    OPTIONAL MATCH depth_path = (owner)-[:OWNS*1..6]->(e)
    WITH e, max(length(depth_path)) AS max_depth
    
    // Check jurisdictions in ownership chain
    OPTIONAL MATCH (e)<-[:OWNS*1..4]-(chain_entity:Entity)
    WITH e, max_depth, 
         count(DISTINCT chain_entity.jurisdiction_code) AS jurisdiction_count
    
    // Check PEP connections
    OPTIONAL MATCH (pep:Person {is_pep: true})-[:OWNS|CONTROLS*1..3]->(e)
    WITH e, max_depth, jurisdiction_count,
         count(DISTINCT pep) AS pep_connections
    
    // Check address concentration
    OPTIONAL MATCH (e)-[:HAS_ADDRESS]->(a:Address)<-[:HAS_ADDRESS]-(other:Entity)
    WHERE other <> e
    WITH e, max_depth, jurisdiction_count, pep_connections,
         count(DISTINCT other) AS shared_address_count
    
    // Get jurisdiction risk
    OPTIONAL MATCH (e)-[:REGISTERED_IN]->(j:Jurisdiction)
    
    RETURN 
        e.entity_id AS entity_id,
        e.name AS name,
        e.jurisdiction_code AS jurisdiction,
        j.is_tax_haven AS is_tax_haven,
        j.secrecy_score AS secrecy_score,
        COALESCE(max_depth, 0) AS layering_depth,
        COALESCE(jurisdiction_count, 0) AS jurisdiction_count,
        COALESCE(pep_connections, 0) AS pep_connections,
        COALESCE(shared_address_count, 0) AS shared_address_count
    LIMIT 1
    """
    
    try:
        result = await session.run(query, {"entity_id": entity_id})
        record = await result.single()
        
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity '{entity_id}' not found",
            )
        
        # Calculate risk score and identify flags
        red_flags: list[RedFlag] = []
        risk_score = 0.0
        
        # Layering depth risk
        layering_depth = record["layering_depth"] or 0
        if layering_depth >= 4:
            risk_score += 25
            red_flags.append(RedFlag(
                flag_type="DEEP_LAYERING",
                severity=RiskLevel.HIGH if layering_depth >= 5 else RiskLevel.MEDIUM,
                description=f"Ownership chain depth of {layering_depth} hops (threshold: 4)",
                evidence=f"Maximum ownership path length: {layering_depth}",
            ))
        
        # Multi-jurisdiction risk
        jurisdiction_count = record["jurisdiction_count"] or 0
        if jurisdiction_count >= 3:
            risk_score += 20
            red_flags.append(RedFlag(
                flag_type="MULTI_JURISDICTION",
                severity=RiskLevel.MEDIUM,
                description=f"Ownership chain crosses {jurisdiction_count} jurisdictions",
            ))
        
        # PEP connections
        pep_connections = record["pep_connections"] or 0
        if pep_connections > 0:
            risk_score += 30
            red_flags.append(RedFlag(
                flag_type="PEP_CONNECTION",
                severity=RiskLevel.HIGH,
                description=f"Connected to {pep_connections} Politically Exposed Person(s)",
            ))
        
        # Tax haven registration
        if record.get("is_tax_haven"):
            risk_score += 15
            red_flags.append(RedFlag(
                flag_type="TAX_HAVEN_REGISTRATION",
                severity=RiskLevel.MEDIUM,
                description=f"Registered in tax haven jurisdiction: {record['jurisdiction']}",
            ))
        
        # High secrecy score
        secrecy_score = record.get("secrecy_score") or 0
        if secrecy_score >= 70:
            risk_score += 10
            red_flags.append(RedFlag(
                flag_type="HIGH_SECRECY_JURISDICTION",
                severity=RiskLevel.MEDIUM,
                description=f"Jurisdiction secrecy score: {secrecy_score}/100",
            ))
        
        # Mass registration address
        shared_address_count = record["shared_address_count"] or 0
        if shared_address_count >= 10:
            risk_score += 20
            red_flags.append(RedFlag(
                flag_type="MASS_REGISTRATION_ADDRESS",
                severity=RiskLevel.HIGH if shared_address_count >= 50 else RiskLevel.MEDIUM,
                description=f"Address shared with {shared_address_count} other entities",
            ))
        
        # Determine overall risk level
        risk_score = min(risk_score, 100)
        if risk_score >= 70:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 50:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 25:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        return RedFlagAnalysis(
            entity_id=entity_id,
            entity_name=record["name"],
            overall_risk_score=risk_score,
            overall_risk_level=risk_level,
            red_flags=red_flags,
            flag_count=len(red_flags),
            layering_depth=layering_depth,
            jurisdiction_count=jurisdiction_count,
            pep_connections=pep_connections,
            mass_registration_address=shared_address_count >= 10,
            analysis_timestamp=datetime.utcnow(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Risk analysis error for {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Risk analysis failed",
        )


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = ["router"]
