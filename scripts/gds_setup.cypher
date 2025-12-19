// ============================================================================
// PANAMA PAPERS - GRAPH DATA SCIENCE (GDS) SETUP
// ============================================================================
//
// Neo4j GDS Library Configuration for Offshore Network Analysis
//
// Purpose:
//   - Create in-memory graph projections for high-performance analytics
//   - Run centrality algorithms to identify influential entities
//   - Detect communities and business networks
//   - Identify suspicious patterns through graph algorithms
//
// Prerequisites:
//   - Neo4j 5.x with GDS plugin installed (2.x recommended)
//   - Sufficient memory (heap + page cache) for graph projections
//   - Panama Papers schema already created and data loaded
//
// Execution Order:
//   1. Verify GDS installation
//   2. Create graph projections
//   3. Run algorithms (stream mode first for testing)
//   4. Write results back to database
//   5. Clean up projections when done
//
// Memory Estimation:
//   - ~1GB RAM per 10M nodes + relationships
//   - Run gds.graph.project.estimate() before large projections
//
// ============================================================================


// ============================================================================
// SECTION 1: GDS LIBRARY VERIFICATION
// ============================================================================
// Verify the GDS plugin is properly installed and check version compatibility

// Check GDS version (should be 2.x for Neo4j 5.x)
CALL gds.version()
YIELD gdsVersion
RETURN gdsVersion AS installed_version;

// Verify GDS is properly licensed (Community vs Enterprise)
CALL gds.debug.sysInfo()
YIELD key, value
WHERE key IN ['gdsVersion', 'gdsEdition', 'availableCPUs', 'heapFree', 'heapTotal']
RETURN key, value;

// List all available algorithms (useful for reference)
CALL gds.list()
YIELD name, description, signature
WITH name, description, signature
WHERE name CONTAINS 'pagerank' 
   OR name CONTAINS 'louvain'
   OR name CONTAINS 'degree'
   OR name CONTAINS 'shortestPath'
   OR name CONTAINS 'betweenness'
RETURN name, description
ORDER BY name;

// Check current graph catalog (existing projections)
CALL gds.graph.list()
YIELD graphName, nodeCount, relationshipCount, creationTime, memoryUsage
RETURN graphName, nodeCount, relationshipCount, creationTime, memoryUsage;


// ============================================================================
// SECTION 2: MEMORY ESTIMATION
// ============================================================================
// Always estimate memory before creating large projections to prevent OOM errors

// Estimate memory for ownership graph projection
CALL gds.graph.project.estimate(
    'Entity',
    {
        OWNS: {
            type: 'OWNS',
            orientation: 'NATURAL',
            properties: ['ownership_percentage']
        }
    }
)
YIELD requiredMemory, nodeCount, relationshipCount
RETURN 
    requiredMemory AS estimated_memory,
    nodeCount AS estimated_nodes,
    relationshipCount AS estimated_relationships;

// Estimate memory for control graph (multi-label)
CALL gds.graph.project.estimate(
    ['Entity', 'Person'],
    ['OWNS', 'CONTROLS', 'INVOLVED_IN']
)
YIELD requiredMemory, nodeCount, relationshipCount
RETURN requiredMemory, nodeCount, relationshipCount;


// ============================================================================
// SECTION 3: GRAPH PROJECTIONS
// ============================================================================
// Create in-memory graph representations optimized for specific analyses
// These projections are stored in the GDS graph catalog

// ----------------------------------------------------------------------------
// PROJECTION 1: OWNERSHIP GRAPH
// ----------------------------------------------------------------------------
// Purpose: Analyze ownership influence, find controlling entities
// Use cases: PageRank, betweenness centrality, path analysis
// Direction: NATURAL (follows OWNS direction: owner -> owned)

// Drop if exists (for re-runs)
CALL gds.graph.drop('ownership-graph', false)
YIELD graphName
RETURN graphName AS dropped;

// Create ownership graph projection
CALL gds.graph.project(
    'ownership-graph',                              // Graph name
    {
        Entity: {                                   // Node projection
            label: 'Entity',
            properties: {
                entity_type: {
                    property: 'entity_type',
                    defaultValue: 'Unknown'
                },
                jurisdiction_code: {
                    property: 'jurisdiction_code',
                    defaultValue: 'UNK'
                },
                status: {
                    property: 'status',
                    defaultValue: 'Unknown'
                }
            }
        },
        Company: {
            label: 'Company',
            properties: {
                jurisdiction_code: {
                    property: 'jurisdiction_code',
                    defaultValue: 'UNK'
                },
                is_shell_company: {
                    property: 'is_shell_company',
                    defaultValue: false
                }
            }
        }
    },
    {
        OWNS: {                                     // Relationship projection
            type: 'OWNS',
            orientation: 'NATURAL',                 // Directed: owner -> owned
            properties: {
                ownership_percentage: {
                    property: 'ownership_percentage',
                    defaultValue: 0.0,
                    aggregation: 'MAX'              // Use max if multiple edges
                }
            }
        }
    }
)
YIELD 
    graphName, 
    nodeCount, 
    relationshipCount, 
    projectMillis,
    configuration
RETURN 
    graphName,
    nodeCount AS nodes,
    relationshipCount AS relationships,
    projectMillis AS creation_time_ms;


// ----------------------------------------------------------------------------
// PROJECTION 2: CONTROL GRAPH (Undirected for Community Detection)
// ----------------------------------------------------------------------------
// Purpose: Detect business networks and communities
// Use cases: Louvain clustering, connected components, triangle counting
// Direction: UNDIRECTED (treats relationships as bidirectional)

CALL gds.graph.drop('control-graph', false)
YIELD graphName
RETURN graphName AS dropped;

CALL gds.graph.project(
    'control-graph',
    {
        Entity: {
            label: 'Entity',
            properties: ['name', 'entity_type', 'jurisdiction_code']
        },
        Person: {
            label: 'Person',
            properties: ['full_name', 'nationality', 'is_pep']
        },
        Company: {
            label: 'Company',
            properties: ['name', 'jurisdiction_code']
        }
    },
    {
        OWNS: {
            type: 'OWNS',
            orientation: 'UNDIRECTED',              // Bidirectional for clustering
            properties: ['ownership_percentage']
        },
        CONTROLS: {
            type: 'CONTROLS',
            orientation: 'UNDIRECTED',
            properties: ['control_type']
        },
        INVOLVED_IN: {
            type: 'INVOLVED_IN',
            orientation: 'UNDIRECTED',
            properties: ['role']
        }
    }
)
YIELD graphName, nodeCount, relationshipCount, projectMillis
RETURN graphName, nodeCount, relationshipCount, projectMillis;


// ----------------------------------------------------------------------------
// PROJECTION 3: JURISDICTION GRAPH
// ----------------------------------------------------------------------------
// Purpose: Geographic risk analysis, jurisdiction hopping detection
// Use cases: Path analysis, jurisdiction clustering

CALL gds.graph.drop('jurisdiction-graph', false)
YIELD graphName
RETURN graphName AS dropped;

CALL gds.graph.project(
    'jurisdiction-graph',
    {
        Entity: {
            label: 'Entity',
            properties: ['name', 'entity_type']
        },
        Jurisdiction: {
            label: 'Jurisdiction',
            properties: {
                is_tax_haven: {
                    property: 'is_tax_haven',
                    defaultValue: false
                },
                risk_level: {
                    property: 'risk_level',
                    defaultValue: 'UNKNOWN'
                },
                secrecy_score: {
                    property: 'secrecy_score',
                    defaultValue: 50
                }
            }
        },
        Address: {
            label: 'Address',
            properties: ['country_code', 'city']
        }
    },
    {
        REGISTERED_IN: {
            type: 'REGISTERED_IN',
            orientation: 'NATURAL'
        },
        HAS_ADDRESS: {
            type: 'HAS_ADDRESS',
            orientation: 'NATURAL'
        }
    }
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;


// ----------------------------------------------------------------------------
// PROJECTION 4: INTERMEDIARY NETWORK
// ----------------------------------------------------------------------------
// Purpose: Identify influential intermediaries (law firms, banks)
// Use cases: PageRank, degree centrality on service providers

CALL gds.graph.drop('intermediary-graph', false)
YIELD graphName
RETURN graphName AS dropped;

CALL gds.graph.project(
    'intermediary-graph',
    {
        Intermediary: {
            label: 'Intermediary',
            properties: ['name', 'type', 'country_code']
        },
        Entity: {
            label: 'Entity',
            properties: ['name', 'jurisdiction_code']
        }
    },
    {
        CREATED_BY: {
            type: 'CREATED_BY',
            orientation: 'REVERSE'                  // Entity -> Intermediary (reversed)
        }
    }
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;


// ============================================================================
// SECTION 4: CENTRALITY ALGORITHMS
// ============================================================================
// Identify influential nodes in the offshore network

// ----------------------------------------------------------------------------
// ALGORITHM 1: PageRank - Ownership Influence
// ----------------------------------------------------------------------------
// Finds entities that are "owned by" many other important entities
// High PageRank = influential/important in ownership network

// Stream mode (returns results without writing)
CALL gds.pageRank.stream(
    'ownership-graph',
    {
        maxIterations: 20,
        dampingFactor: 0.85,
        tolerance: 0.0001,
        relationshipWeightProperty: 'ownership_percentage',
        scaler: 'MEAN'                              // Normalize scores
    }
)
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS entity, score
WHERE score > 0.001                                 // Filter low-influence nodes
RETURN 
    entity.entity_id AS entity_id,
    entity.name AS entity_name,
    entity.jurisdiction_code AS jurisdiction,
    entity.entity_type AS type,
    round(score * 1000) / 1000 AS pagerank_score
ORDER BY pagerank_score DESC
LIMIT 25;


// ----------------------------------------------------------------------------
// ALGORITHM 2: Betweenness Centrality - Bridge Entities
// ----------------------------------------------------------------------------
// Identifies entities that act as bridges between different parts of the network
// High betweenness = critical intermediary in ownership chains

CALL gds.betweenness.stream(
    'ownership-graph',
    {
        samplingSize: 10000,                        // Sample for large graphs
        samplingSeed: 42
    }
)
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS entity, score
WHERE score > 0
RETURN 
    entity.name AS entity_name,
    entity.jurisdiction_code AS jurisdiction,
    round(score) AS betweenness_score
ORDER BY betweenness_score DESC
LIMIT 20;


// ----------------------------------------------------------------------------
// ALGORITHM 3: Degree Centrality - Network Hubs
// ----------------------------------------------------------------------------
// Simple count of connections - finds most connected entities

CALL gds.degree.stream(
    'control-graph',
    {
        orientation: 'UNDIRECTED'
    }
)
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score
WHERE score >= 5                                    // At least 5 connections
RETURN 
    labels(node)[0] AS node_type,
    COALESCE(node.name, node.full_name) AS name,
    toInteger(score) AS connection_count
ORDER BY connection_count DESC
LIMIT 30;


// ----------------------------------------------------------------------------
// ALGORITHM 4: Eigenvector Centrality - Connected to Important Nodes
// ----------------------------------------------------------------------------
// Similar to PageRank but emphasizes connections to high-scoring nodes

CALL gds.eigenvector.stream(
    'ownership-graph',
    {
        maxIterations: 100,
        tolerance: 0.0001
    }
)
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS entity, score
WHERE score > 0.01
RETURN 
    entity.name AS entity_name,
    entity.jurisdiction_code AS jurisdiction,
    round(score * 1000) / 1000 AS eigenvector_score
ORDER BY eigenvector_score DESC
LIMIT 20;


// ============================================================================
// SECTION 5: COMMUNITY DETECTION
// ============================================================================
// Identify clusters of related entities (business networks, family holdings)

// ----------------------------------------------------------------------------
// ALGORITHM 5: Louvain Community Detection
// ----------------------------------------------------------------------------
// Detects dense communities/clusters in the network
// Useful for identifying business groups operating together

CALL gds.louvain.stream(
    'control-graph',
    {
        maxLevels: 10,
        maxIterations: 10,
        tolerance: 0.0001,
        includeIntermediateCommunities: false,
        consecutiveIds: true,
        seedProperty: null,
        relationshipWeightProperty: null
    }
)
YIELD nodeId, communityId, intermediateCommunityIds
WITH communityId, collect(gds.util.asNode(nodeId)) AS members
WITH 
    communityId,
    size(members) AS community_size,
    [m IN members | COALESCE(m.name, m.full_name)][0..10] AS sample_members,
    [m IN members WHERE m:Person | m.full_name][0..5] AS persons_in_community,
    [m IN members WHERE m:Entity | m.jurisdiction_code][0..5] AS jurisdictions
WHERE community_size >= 3                           // Minimum cluster size
RETURN 
    communityId AS community_id,
    community_size,
    sample_members,
    persons_in_community,
    jurisdictions
ORDER BY community_size DESC
LIMIT 25;


// ----------------------------------------------------------------------------
// ALGORITHM 6: Weakly Connected Components
// ----------------------------------------------------------------------------
// Finds isolated subgraphs (disconnected business networks)

CALL gds.wcc.stream('control-graph')
YIELD nodeId, componentId
WITH componentId, collect(gds.util.asNode(nodeId)) AS nodes
WITH 
    componentId,
    size(nodes) AS component_size,
    [n IN nodes | COALESCE(n.name, n.full_name)][0..5] AS sample_nodes
WHERE component_size >= 2 AND component_size <= 100  // Mid-sized components
RETURN 
    componentId AS component_id,
    component_size,
    sample_nodes
ORDER BY component_size DESC
LIMIT 20;


// ----------------------------------------------------------------------------
// ALGORITHM 7: Label Propagation (Fast Community Detection)
// ----------------------------------------------------------------------------
// Faster alternative to Louvain for very large graphs

CALL gds.labelPropagation.stream(
    'control-graph',
    {
        maxIterations: 10,
        nodeWeightProperty: null,
        relationshipWeightProperty: null
    }
)
YIELD nodeId, communityId
WITH communityId, count(*) AS size
WHERE size >= 5
RETURN communityId, size
ORDER BY size DESC
LIMIT 20;


// ============================================================================
// SECTION 6: PATH ANALYSIS ALGORITHMS
// ============================================================================
// Analyze ownership chains and connections

// ----------------------------------------------------------------------------
// ALGORITHM 8: All Pairs Shortest Path (Sample)
// ----------------------------------------------------------------------------
// Find shortest ownership paths between entities
// WARNING: Expensive on large graphs - use with filters

CALL gds.allShortestPaths.stream(
    'ownership-graph',
    {
        sourceNode: null,                           // All pairs
        relationshipWeightProperty: null
    }
)
YIELD sourceNodeId, targetNodeId, distance
WITH 
    gds.util.asNode(sourceNodeId) AS source,
    gds.util.asNode(targetNodeId) AS target,
    distance
WHERE distance > 0 AND distance <= 4                // 1-4 hop paths
  AND source.entity_type = 'Company'
  AND target.entity_type = 'Company'
RETURN 
    source.name AS from_entity,
    target.name AS to_entity,
    toInteger(distance) AS path_length
ORDER BY path_length DESC
LIMIT 20;


// ============================================================================
// SECTION 7: WRITE RESULTS BACK TO DATABASE
// ============================================================================
// Persist algorithm results as node properties for future queries

// ----------------------------------------------------------------------------
// Write PageRank scores to Entity nodes
// ----------------------------------------------------------------------------
CALL gds.pageRank.write(
    'ownership-graph',
    {
        maxIterations: 20,
        dampingFactor: 0.85,
        writeProperty: 'pagerank_score'
    }
)
YIELD 
    nodePropertiesWritten,
    ranIterations,
    didConverge,
    preProcessingMillis,
    computeMillis,
    writeMillis,
    centralityDistribution
RETURN 
    nodePropertiesWritten AS nodes_updated,
    ranIterations AS iterations,
    didConverge AS converged,
    computeMillis AS compute_time_ms,
    writeMillis AS write_time_ms,
    centralityDistribution.mean AS mean_score,
    centralityDistribution.max AS max_score;


// ----------------------------------------------------------------------------
// Write Louvain community IDs to nodes
// ----------------------------------------------------------------------------
CALL gds.louvain.write(
    'control-graph',
    {
        writeProperty: 'community_id',
        maxLevels: 10,
        maxIterations: 10
    }
)
YIELD 
    communityCount,
    nodePropertiesWritten,
    modularity,
    computeMillis,
    writeMillis
RETURN 
    communityCount AS communities_found,
    nodePropertiesWritten AS nodes_updated,
    round(modularity * 1000) / 1000 AS modularity_score,
    computeMillis + writeMillis AS total_time_ms;


// ----------------------------------------------------------------------------
// Write Degree Centrality scores
// ----------------------------------------------------------------------------
CALL gds.degree.write(
    'control-graph',
    {
        writeProperty: 'degree_centrality',
        orientation: 'UNDIRECTED'
    }
)
YIELD 
    nodePropertiesWritten,
    centralityDistribution
RETURN 
    nodePropertiesWritten AS nodes_updated,
    centralityDistribution.mean AS mean_degree,
    centralityDistribution.max AS max_degree;


// ----------------------------------------------------------------------------
// Write Betweenness Centrality scores (sampling for performance)
// ----------------------------------------------------------------------------
CALL gds.betweenness.write(
    'ownership-graph',
    {
        writeProperty: 'betweenness_score',
        samplingSize: 5000,
        samplingSeed: 42
    }
)
YIELD 
    nodePropertiesWritten,
    centralityDistribution
RETURN 
    nodePropertiesWritten AS nodes_updated,
    centralityDistribution.max AS max_betweenness;


// ============================================================================
// SECTION 8: VERIFICATION QUERIES
// ============================================================================
// Verify algorithm results were written correctly

// Check PageRank scores were written
MATCH (e:Entity)
WHERE e.pagerank_score IS NOT NULL
RETURN 
    'PageRank' AS algorithm,
    count(e) AS nodes_with_scores,
    avg(e.pagerank_score) AS avg_score,
    max(e.pagerank_score) AS max_score;

// Check community assignments
MATCH (n)
WHERE n.community_id IS NOT NULL
RETURN 
    'Louvain' AS algorithm,
    count(DISTINCT n.community_id) AS total_communities,
    count(n) AS nodes_assigned;

// Check degree centrality
MATCH (n)
WHERE n.degree_centrality IS NOT NULL
WITH n
ORDER BY n.degree_centrality DESC
LIMIT 10
RETURN 
    labels(n)[0] AS node_type,
    COALESCE(n.name, n.full_name) AS name,
    n.degree_centrality AS degree,
    n.pagerank_score AS pagerank,
    n.community_id AS community;


// ============================================================================
// SECTION 9: ANALYTICAL QUERIES USING GDS RESULTS
// ============================================================================
// Use the written properties for business analysis

// Find high-influence entities in each jurisdiction
MATCH (e:Entity)
WHERE e.pagerank_score IS NOT NULL
WITH e.jurisdiction_code AS jurisdiction, e
ORDER BY e.pagerank_score DESC
WITH jurisdiction, collect(e)[0..3] AS top_entities
UNWIND top_entities AS entity
RETURN 
    jurisdiction,
    entity.name AS entity_name,
    round(entity.pagerank_score * 1000) / 1000 AS influence_score
ORDER BY jurisdiction, influence_score DESC;

// Find communities spanning multiple jurisdictions (suspicious pattern)
MATCH (e:Entity)
WHERE e.community_id IS NOT NULL AND e.jurisdiction_code IS NOT NULL
WITH e.community_id AS community, collect(DISTINCT e.jurisdiction_code) AS jurisdictions
WHERE size(jurisdictions) >= 3                      // 3+ jurisdictions
RETURN 
    community AS community_id,
    size(jurisdictions) AS jurisdiction_count,
    jurisdictions AS jurisdictions_list
ORDER BY jurisdiction_count DESC
LIMIT 15;

// Find highly connected entities in same community as PEPs
MATCH (pep:Person {is_pep: true})
WHERE pep.community_id IS NOT NULL
WITH pep.community_id AS pep_community, pep
MATCH (e:Entity {community_id: pep_community})
WHERE e.degree_centrality > 5
RETURN 
    pep.full_name AS pep_name,
    e.name AS connected_entity,
    e.jurisdiction_code AS jurisdiction,
    e.degree_centrality AS connections,
    e.pagerank_score AS influence
ORDER BY e.pagerank_score DESC
LIMIT 20;


// ============================================================================
// SECTION 10: GRAPH CATALOG MANAGEMENT
// ============================================================================
// Manage in-memory graph projections

// List all current projections with details
CALL gds.graph.list()
YIELD 
    graphName, 
    database,
    nodeCount, 
    relationshipCount, 
    density,
    creationTime,
    modificationTime,
    memoryUsage
RETURN 
    graphName,
    nodeCount AS nodes,
    relationshipCount AS relationships,
    round(density * 10000) / 10000 AS density,
    memoryUsage AS memory,
    creationTime
ORDER BY nodeCount DESC;

// Get detailed stats for a specific projection
CALL gds.graph.nodeProperties.stream('ownership-graph', 'entity_type')
YIELD nodeId, propertyValue
WITH propertyValue, count(*) AS count
RETURN propertyValue AS entity_type, count
ORDER BY count DESC;


// ============================================================================
// SECTION 11: CLEANUP - DROP GRAPH PROJECTIONS
// ============================================================================
// Release memory by dropping projections when analysis is complete
// Uncomment these lines when you want to clean up

// Drop ownership graph
// CALL gds.graph.drop('ownership-graph', false)
// YIELD graphName
// RETURN 'Dropped: ' + graphName AS status;

// Drop control graph
// CALL gds.graph.drop('control-graph', false)
// YIELD graphName
// RETURN 'Dropped: ' + graphName AS status;

// Drop jurisdiction graph
// CALL gds.graph.drop('jurisdiction-graph', false)
// YIELD graphName
// RETURN 'Dropped: ' + graphName AS status;

// Drop intermediary graph
// CALL gds.graph.drop('intermediary-graph', false)
// YIELD graphName
// RETURN 'Dropped: ' + graphName AS status;

// Drop ALL projections (use with caution)
// CALL gds.graph.list() YIELD graphName
// CALL gds.graph.drop(graphName, false) YIELD graphName AS dropped
// RETURN dropped;


// ============================================================================
// SECTION 12: INDEX RECOMMENDATIONS FOR GDS PROPERTIES
// ============================================================================
// Create indexes on algorithm-generated properties for faster queries

// Index for PageRank score lookups
CREATE INDEX entity_pagerank_idx IF NOT EXISTS
FOR (e:Entity) ON (e.pagerank_score);

// Index for community-based queries
CREATE INDEX entity_community_idx IF NOT EXISTS
FOR (e:Entity) ON (e.community_id);

CREATE INDEX person_community_idx IF NOT EXISTS
FOR (p:Person) ON (p.community_id);

// Index for degree centrality filtering
CREATE INDEX entity_degree_idx IF NOT EXISTS
FOR (e:Entity) ON (e.degree_centrality);

// Composite index for influence + jurisdiction analysis
CREATE INDEX entity_pagerank_jurisdiction_idx IF NOT EXISTS
FOR (e:Entity) ON (e.jurisdiction_code, e.pagerank_score);


// ============================================================================
// GDS SETUP COMPLETE
// ============================================================================
//
// Summary of Projections Created:
//   1. ownership-graph    - Directed OWNS network for centrality
//   2. control-graph      - Undirected multi-relationship for clustering
//   3. jurisdiction-graph - Entity-Jurisdiction connections
//   4. intermediary-graph - Service provider network
//
// Algorithms Executed:
//   - PageRank (ownership influence)
//   - Betweenness Centrality (bridge detection)
//   - Degree Centrality (network hubs)
//   - Eigenvector Centrality (connected to important nodes)
//   - Louvain (community detection)
//   - WCC (connected components)
//   - Label Propagation (fast clustering)
//
// Properties Written:
//   - pagerank_score     (Entity nodes)
//   - community_id       (Entity, Person nodes)
//   - degree_centrality  (Entity, Person nodes)
//   - betweenness_score  (Entity nodes)
//
// Next Steps:
//   1. Run analytical queries in Section 9
//   2. Build visualizations on community_id groupings
//   3. Create alerts for high-influence + tax haven combinations
//   4. Export results for external analysis tools
//
// ============================================================================
