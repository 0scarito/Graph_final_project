// ============================================================================
// PANAMA PAPERS - ANALYSIS QUERIES
// ============================================================================
//
// Neo4j 5.x Cypher queries for offshore financial network analysis
//
// Categories:
//   1. Beneficial Ownership Tracing
//   2. Red Flag Detection
//   3. Intermediary Analysis
//   4. Jurisdiction Risk Analysis
//   5. Network Pattern Detection
//
// Performance Notes:
//   - All queries include LIMIT clauses to prevent runaway execution
//   - Use EXPLAIN or PROFILE prefix to analyze query plans
//   - Ensure indexes exist on filtered properties (see schema.cypher)
//   - Variable-length paths bounded to prevent memory issues
//
// ============================================================================


// ============================================================================
// QUERY 1: BENEFICIAL OWNERSHIP TRACING
// ============================================================================
// Purpose: Find ownership chain from entity to ultimate beneficial owners
// Direction: Entity <- OWNS <- ... <- Person (reverse traversal)
// Expected Time: ~50-200ms depending on graph density

// 1.1 - Simple beneficial owner lookup (2-4 hops)
// Finds all persons who own the target entity through any chain
MATCH path = (beneficial:Person)-[:OWNS*1..4]->(target:Entity)
WHERE target.entity_id = $entityId
WITH 
    beneficial,
    path,
    length(path) AS depth,
    [r IN relationships(path) | r.ownership_percentage] AS percentages
RETURN 
    beneficial.full_name AS beneficial_owner,
    beneficial.nationality AS nationality,
    beneficial.is_pep AS is_pep,
    depth AS ownership_depth,
    percentages AS ownership_chain,
    REDUCE(pct = 100.0, p IN percentages | pct * COALESCE(p, 100.0) / 100.0) AS effective_ownership
ORDER BY effective_ownership DESC, depth ASC
LIMIT 20;


// 1.2 - Beneficial ownership with intermediate entities
// Shows each entity in the ownership chain
MATCH path = (person:Person)-[:OWNS*1..4]->(target:Entity {entity_id: $entityId})
WITH 
    person,
    nodes(path) AS chain_nodes,
    relationships(path) AS chain_rels,
    length(path) AS depth
UNWIND range(0, size(chain_nodes) - 1) AS idx
WITH 
    person,
    depth,
    idx,
    chain_nodes[idx] AS node,
    CASE WHEN idx < size(chain_rels) THEN chain_rels[idx] ELSE null END AS rel
RETURN 
    person.full_name AS beneficial_owner,
    depth AS total_depth,
    idx AS layer,
    COALESCE(node.name, node.full_name) AS entity_name,
    labels(node)[0] AS entity_type,
    node.jurisdiction_code AS jurisdiction,
    rel.ownership_percentage AS ownership_pct
ORDER BY person.full_name, idx
LIMIT 100;


// 1.3 - All shortest paths to beneficial owners
// Finds the shortest ownership paths (most direct control)
MATCH (target:Entity {entity_id: $entityId})
MATCH (person:Person)
WHERE (person)-[:OWNS*1..6]->(target)
MATCH path = shortestPath((person)-[:OWNS*1..6]->(target))
WITH person, path, length(path) AS depth
RETURN 
    person.full_name AS owner,
    person.nationality AS nationality,
    depth,
    [n IN nodes(path) | COALESCE(n.name, n.full_name)] AS ownership_chain
ORDER BY depth ASC
LIMIT 15;


// 1.4 - Ownership tree (all downstream entities from a person)
// Finds everything a person owns directly or indirectly
MATCH path = (person:Person {person_id: $personId})-[:OWNS*1..5]->(owned)
WITH 
    owned,
    length(path) AS depth,
    [r IN relationships(path) | r.ownership_percentage] AS percentages
WITH 
    owned,
    depth,
    REDUCE(pct = 100.0, p IN percentages | pct * COALESCE(p, 100.0) / 100.0) AS effective_pct
RETURN 
    owned.entity_id AS entity_id,
    owned.name AS entity_name,
    owned.jurisdiction_code AS jurisdiction,
    owned.entity_type AS type,
    depth AS layers_deep,
    round(effective_pct * 100) / 100 AS effective_ownership_pct
ORDER BY depth, effective_pct DESC
LIMIT 50;


// ============================================================================
// QUERY 2: RED FLAG DETECTION
// ============================================================================
// Purpose: Identify suspicious patterns indicating potential money laundering,
// tax evasion, or other financial crimes

// 2.1 - Deep ownership layering (4+ hops = high risk)
// Excessive layering often indicates intent to obscure ownership
MATCH path = (p:Person)-[:OWNS*4..8]->(e:Entity)
WITH 
    p, 
    e, 
    length(path) AS depth,
    [n IN nodes(path) WHERE n:Entity | n.jurisdiction_code] AS jurisdictions
WITH 
    p,
    e,
    depth,
    jurisdictions,
    size(apoc.coll.toSet(jurisdictions)) AS unique_jurisdictions
RETURN 
    p.full_name AS beneficial_owner,
    p.nationality AS nationality,
    p.is_pep AS is_pep,
    e.name AS end_entity,
    depth AS layering_depth,
    unique_jurisdictions AS jurisdictions_used,
    jurisdictions AS jurisdiction_chain,
    CASE 
        WHEN depth >= 6 AND unique_jurisdictions >= 4 THEN 'CRITICAL'
        WHEN depth >= 5 OR unique_jurisdictions >= 3 THEN 'HIGH'
        WHEN depth >= 4 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_level
ORDER BY depth DESC, unique_jurisdictions DESC
LIMIT 25;


// 2.2 - Circular ownership detection
// Entities that own themselves through chains (shell company networks)
MATCH path = (e:Entity)-[:OWNS*2..6]->(e)
WITH 
    e,
    path,
    length(path) AS cycle_length,
    [n IN nodes(path) | n.name] AS cycle_entities
RETURN 
    e.name AS entity_name,
    e.jurisdiction_code AS jurisdiction,
    cycle_length,
    cycle_entities,
    'CIRCULAR_OWNERSHIP' AS red_flag
ORDER BY cycle_length ASC
LIMIT 20;


// 2.3 - Multi-jurisdiction hopping
// Entities with ownership chains crossing 3+ tax havens
MATCH (j:Jurisdiction {is_tax_haven: true})
WITH collect(j.jurisdiction_code) AS tax_havens
MATCH path = (p:Person)-[:OWNS*2..5]->(e:Entity)
WITH 
    p, e, path, tax_havens,
    [n IN nodes(path) WHERE n:Entity | n.jurisdiction_code] AS chain_jurisdictions
WITH 
    p, e,
    [j IN chain_jurisdictions WHERE j IN tax_havens] AS haven_crossings,
    chain_jurisdictions
WHERE size(haven_crossings) >= 3
RETURN 
    p.full_name AS owner,
    e.name AS end_entity,
    chain_jurisdictions AS full_chain,
    haven_crossings AS tax_havens_used,
    size(haven_crossings) AS haven_count,
    'JURISDICTION_SHOPPING' AS red_flag
ORDER BY size(haven_crossings) DESC
LIMIT 20;


// 2.4 - Nominee address concentration
// Many entities at same address (indicates shell companies)
MATCH (a:Address)<-[:HAS_ADDRESS]-(e:Entity)
WITH a, collect(e) AS entities, count(e) AS entity_count
WHERE entity_count >= 10
RETURN 
    a.full_address AS address,
    a.country_code AS country,
    entity_count AS entities_at_address,
    [ent IN entities[0..10] | ent.name] AS sample_entities,
    CASE 
        WHEN entity_count >= 100 THEN 'CRITICAL'
        WHEN entity_count >= 50 THEN 'HIGH'
        WHEN entity_count >= 20 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_level,
    'MASS_REGISTRATION_ADDRESS' AS red_flag
ORDER BY entity_count DESC
LIMIT 20;


// 2.5 - PEP (Politically Exposed Person) connections
// Find entities connected to politically exposed persons
MATCH (pep:Person {is_pep: true})-[r:OWNS|CONTROLS|INVOLVED_IN*1..3]->(e:Entity)
WITH 
    pep,
    e,
    length(r) AS connection_depth,
    [rel IN r | type(rel)] AS relationship_types
MATCH (e)-[:REGISTERED_IN]->(j:Jurisdiction)
RETURN 
    pep.full_name AS pep_name,
    pep.pep_details AS political_role,
    e.name AS connected_entity,
    e.entity_type AS entity_type,
    j.name AS jurisdiction,
    j.is_tax_haven AS is_tax_haven,
    connection_depth,
    relationship_types,
    'PEP_CONNECTION' AS red_flag
ORDER BY j.is_tax_haven DESC, connection_depth ASC
LIMIT 30;


// 2.6 - Rapid entity creation (bulk formation)
// Entities created in same week by same intermediary
MATCH (i:Intermediary)<-[:CREATED_BY]-(e:Entity)
WHERE e.incorporation_date IS NOT NULL
WITH 
    i,
    date(e.incorporation_date).week AS week,
    date(e.incorporation_date).year AS year,
    collect(e) AS entities
WITH 
    i,
    year,
    week,
    entities,
    size(entities) AS batch_size
WHERE batch_size >= 5
RETURN 
    i.name AS intermediary,
    i.country_code AS country,
    year,
    week,
    batch_size AS entities_created,
    [ent IN entities[0..5] | ent.name] AS sample_entities,
    'BULK_FORMATION' AS red_flag
ORDER BY batch_size DESC
LIMIT 20;


// ============================================================================
// QUERY 3: INTERMEDIARY ANALYSIS
// ============================================================================
// Purpose: Identify influential intermediaries (law firms, banks, accountants)
// who facilitate offshore structures

// 3.1 - Top intermediaries by entity count
MATCH (i:Intermediary)<-[:CREATED_BY]-(e:Entity)
WITH i, count(e) AS entity_count, collect(DISTINCT e.jurisdiction_code) AS jurisdictions
RETURN 
    i.name AS intermediary_name,
    i.type AS intermediary_type,
    i.country_code AS country,
    entity_count AS entities_created,
    size(jurisdictions) AS jurisdictions_served,
    jurisdictions[0..10] AS top_jurisdictions
ORDER BY entity_count DESC
LIMIT 25;


// 3.2 - Intermediary specialization (jurisdiction focus)
MATCH (i:Intermediary)<-[:CREATED_BY]-(e:Entity)-[:REGISTERED_IN]->(j:Jurisdiction)
WITH i, j, count(e) AS entity_count
ORDER BY entity_count DESC
WITH i, collect({jurisdiction: j.name, count: entity_count})[0..5] AS top_jurisdictions
RETURN 
    i.name AS intermediary,
    i.type AS type,
    top_jurisdictions
ORDER BY top_jurisdictions[0].count DESC
LIMIT 20;


// 3.3 - Intermediaries serving PEPs
MATCH (pep:Person {is_pep: true})-[:OWNS|CONTROLS*1..2]->(e:Entity)-[:CREATED_BY]->(i:Intermediary)
WITH i, collect(DISTINCT pep) AS peps, count(DISTINCT e) AS entities
RETURN 
    i.name AS intermediary,
    i.country_code AS country,
    size(peps) AS pep_clients,
    [p IN peps[0..5] | p.full_name] AS sample_peps,
    entities AS entities_for_peps,
    'PEP_SERVICE_PROVIDER' AS flag
ORDER BY size(peps) DESC
LIMIT 15;


// 3.4 - Intermediary network (shared clients)
// Find intermediaries that share clients with other intermediaries
MATCH (i1:Intermediary)<-[:CREATED_BY]-(e:Entity)-[:CREATED_BY]->(i2:Intermediary)
WHERE i1 <> i2
WITH i1, i2, count(e) AS shared_entities
WHERE shared_entities >= 5
RETURN 
    i1.name AS intermediary_1,
    i2.name AS intermediary_2,
    shared_entities AS shared_clients
ORDER BY shared_entities DESC
LIMIT 20;


// ============================================================================
// QUERY 4: JURISDICTION RISK ANALYSIS
// ============================================================================
// Purpose: Analyze geographic patterns and identify high-risk jurisdiction usage

// 4.1 - Jurisdiction statistics
MATCH (e:Entity)-[:REGISTERED_IN]->(j:Jurisdiction)
WITH j, count(e) AS entity_count
OPTIONAL MATCH (e2:Entity)-[:REGISTERED_IN]->(j)
WHERE e2.status = 'Active'
WITH j, entity_count, count(e2) AS active_count
RETURN 
    j.jurisdiction_code AS code,
    j.name AS jurisdiction,
    j.is_tax_haven AS tax_haven,
    j.secrecy_score AS secrecy_score,
    j.risk_level AS risk_level,
    entity_count AS total_entities,
    active_count AS active_entities,
    round(active_count * 100.0 / entity_count) AS active_pct
ORDER BY entity_count DESC
LIMIT 25;


// 4.2 - Jurisdiction flow analysis
// Where does money flow between jurisdictions?
MATCH (e1:Entity)-[:OWNS]->(e2:Entity)
WHERE e1.jurisdiction_code IS NOT NULL AND e2.jurisdiction_code IS NOT NULL
WITH e1.jurisdiction_code AS from_j, e2.jurisdiction_code AS to_j, count(*) AS flow_count
WHERE from_j <> to_j AND flow_count >= 10
RETURN 
    from_j AS from_jurisdiction,
    to_j AS to_jurisdiction,
    flow_count AS ownership_connections
ORDER BY flow_count DESC
LIMIT 30;


// 4.3 - Tax haven chains
// Ownership paths that cross multiple tax havens
MATCH (j1:Jurisdiction {is_tax_haven: true})<-[:REGISTERED_IN]-(e1:Entity)
      -[:OWNS]->(e2:Entity)-[:REGISTERED_IN]->(j2:Jurisdiction {is_tax_haven: true})
WHERE j1 <> j2
WITH j1, j2, count(*) AS chain_count
RETURN 
    j1.name AS from_haven,
    j2.name AS to_haven,
    chain_count AS ownership_chains
ORDER BY chain_count DESC
LIMIT 20;


// 4.4 - Nationality vs jurisdiction mismatch
// Persons owning entities in different jurisdictions than their nationality
MATCH (p:Person)-[:OWNS*1..2]->(e:Entity)-[:REGISTERED_IN]->(j:Jurisdiction)
WHERE p.nationality IS NOT NULL 
  AND p.nationality <> j.jurisdiction_code
  AND j.is_tax_haven = true
WITH p, j, count(e) AS entity_count
WHERE entity_count >= 2
RETURN 
    p.full_name AS owner,
    p.nationality AS nationality,
    j.name AS offshore_jurisdiction,
    entity_count AS entities_owned,
    'OFFSHORE_MISMATCH' AS pattern
ORDER BY entity_count DESC
LIMIT 25;


// ============================================================================
// QUERY 5: NETWORK PATTERN DETECTION
// ============================================================================
// Purpose: Identify structural patterns in the ownership network

// 5.1 - Hub entities (highly connected)
// Entities with many incoming and outgoing ownership links
MATCH (e:Entity)
OPTIONAL MATCH (e)<-[:OWNS]-(owner)
OPTIONAL MATCH (e)-[:OWNS]->(owned)
WITH e, count(DISTINCT owner) AS owners, count(DISTINCT owned) AS subsidiaries
WITH e, owners, subsidiaries, owners + subsidiaries AS total_connections
WHERE total_connections >= 5
RETURN 
    e.name AS entity_name,
    e.entity_type AS type,
    e.jurisdiction_code AS jurisdiction,
    owners AS owner_count,
    subsidiaries AS subsidiary_count,
    total_connections,
    CASE 
        WHEN owners > subsidiaries * 2 THEN 'HOLDING_COMPANY'
        WHEN subsidiaries > owners * 2 THEN 'INVESTMENT_VEHICLE'
        ELSE 'INTERMEDIATE_HOLDER'
    END AS entity_role
ORDER BY total_connections DESC
LIMIT 30;


// 5.2 - Star pattern detection
// Entities owned by single person through multiple intermediaries
MATCH (p:Person)-[:OWNS]->(intermediate:Entity)-[:OWNS]->(target:Entity)
WITH p, target, collect(DISTINCT intermediate) AS intermediates
WHERE size(intermediates) >= 3
RETURN 
    p.full_name AS owner,
    target.name AS target_entity,
    size(intermediates) AS intermediate_count,
    [i IN intermediates[0..5] | i.name] AS intermediate_entities,
    'STAR_PATTERN' AS structure_type
ORDER BY size(intermediates) DESC
LIMIT 20;


// 5.3 - Parallel structure detection
// Same person owning similar entities in multiple jurisdictions
MATCH (p:Person)-[:OWNS]->(e1:Entity)-[:REGISTERED_IN]->(j1:Jurisdiction)
MATCH (p)-[:OWNS]->(e2:Entity)-[:REGISTERED_IN]->(j2:Jurisdiction)
WHERE e1 <> e2 
  AND j1 <> j2
  AND e1.entity_type = e2.entity_type
WITH p, collect(DISTINCT j1.jurisdiction_code) + collect(DISTINCT j2.jurisdiction_code) AS all_jurisdictions
WITH p, apoc.coll.toSet(all_jurisdictions) AS unique_jurisdictions
WHERE size(unique_jurisdictions) >= 3
RETURN 
    p.full_name AS owner,
    size(unique_jurisdictions) AS jurisdiction_count,
    unique_jurisdictions AS jurisdictions,
    'PARALLEL_STRUCTURES' AS pattern
ORDER BY size(unique_jurisdictions) DESC
LIMIT 20;


// 5.4 - Officer overlap analysis
// Entities sharing multiple officers (indicates common control)
MATCH (e1:Entity)<-[:INVOLVED_IN]-(o:Officer)-[:INVOLVED_IN]->(e2:Entity)
WHERE e1 <> e2
WITH e1, e2, collect(DISTINCT o) AS shared_officers
WHERE size(shared_officers) >= 2
RETURN 
    e1.name AS entity_1,
    e2.name AS entity_2,
    e1.jurisdiction_code AS j1,
    e2.jurisdiction_code AS j2,
    size(shared_officers) AS shared_officer_count,
    [o IN shared_officers | o.name] AS officers,
    'COMMON_CONTROL' AS indicator
ORDER BY size(shared_officers) DESC
LIMIT 25;


// ============================================================================
// QUERY 6: TEMPORAL ANALYSIS
// ============================================================================
// Purpose: Analyze changes over time

// 6.1 - Entity creation timeline
MATCH (e:Entity)
WHERE e.incorporation_date IS NOT NULL
WITH date(e.incorporation_date).year AS year, count(e) AS created
WHERE year >= 1990 AND year <= 2020
RETURN year, created
ORDER BY year;


// 6.2 - Ownership changes around key dates
// Find entities with ownership changes near a specific date
WITH date('2015-04-01') AS leak_date  // Panama Papers leak date
MATCH (e:Entity)<-[r:OWNS]-(owner)
WHERE r.acquisition_date IS NOT NULL
  AND abs(duration.between(date(r.acquisition_date), leak_date).days) <= 90
RETURN 
    e.name AS entity,
    owner.full_name AS owner,
    r.acquisition_date AS ownership_date,
    duration.between(date(r.acquisition_date), leak_date).days AS days_from_leak,
    CASE 
        WHEN date(r.acquisition_date) < leak_date THEN 'BEFORE_LEAK'
        ELSE 'AFTER_LEAK'
    END AS timing
ORDER BY r.acquisition_date
LIMIT 30;


// 6.3 - Dissolution patterns
// Entities dissolved after Panama Papers leak
MATCH (e:Entity)
WHERE e.struck_off_date IS NOT NULL
  AND date(e.struck_off_date) >= date('2016-04-01')
  AND date(e.struck_off_date) <= date('2017-12-31')
OPTIONAL MATCH (e)<-[:OWNS]-(owner:Person)
RETURN 
    e.name AS entity,
    e.jurisdiction_code AS jurisdiction,
    e.struck_off_date AS dissolution_date,
    collect(DISTINCT owner.full_name)[0..3] AS former_owners,
    'POST_LEAK_DISSOLUTION' AS pattern
ORDER BY e.struck_off_date
LIMIT 30;


// ============================================================================
// QUERY 7: SEARCH & LOOKUP UTILITIES
// ============================================================================
// Purpose: Common search patterns for investigation

// 7.1 - Full-text entity search
CALL db.index.fulltext.queryNodes('entity_name_fulltext', $searchTerm)
YIELD node, score
WHERE score > 0.5
WITH node, score
OPTIONAL MATCH (node)-[:REGISTERED_IN]->(j:Jurisdiction)
RETURN 
    node.entity_id AS id,
    node.name AS name,
    node.entity_type AS type,
    j.name AS jurisdiction,
    node.status AS status,
    round(score * 100) / 100 AS relevance
ORDER BY score DESC
LIMIT 20;


// 7.2 - Person search with connections
CALL db.index.fulltext.queryNodes('person_name_fulltext', $personName)
YIELD node AS person, score
WHERE score > 0.5
OPTIONAL MATCH (person)-[r:OWNS|CONTROLS|INVOLVED_IN]->(e:Entity)
WITH person, score, count(e) AS entity_count, collect(e.name)[0..5] AS sample_entities
RETURN 
    person.person_id AS id,
    person.full_name AS name,
    person.nationality AS nationality,
    person.is_pep AS is_pep,
    entity_count AS connected_entities,
    sample_entities,
    round(score * 100) / 100 AS relevance
ORDER BY score DESC
LIMIT 15;


// 7.3 - Entity profile (comprehensive lookup)
MATCH (e:Entity {entity_id: $entityId})
OPTIONAL MATCH (e)-[:REGISTERED_IN]->(j:Jurisdiction)
OPTIONAL MATCH (e)-[:HAS_ADDRESS]->(a:Address)
OPTIONAL MATCH (e)-[:CREATED_BY]->(i:Intermediary)
OPTIONAL MATCH (owner)-[:OWNS]->(e)
OPTIONAL MATCH (e)-[:OWNS]->(subsidiary)
OPTIONAL MATCH (officer)-[:INVOLVED_IN]->(e)
RETURN 
    e.entity_id AS id,
    e.name AS name,
    e.entity_type AS type,
    e.status AS status,
    e.incorporation_date AS incorporated,
    j.name AS jurisdiction,
    j.is_tax_haven AS tax_haven,
    a.full_address AS address,
    i.name AS intermediary,
    count(DISTINCT owner) AS owner_count,
    count(DISTINCT subsidiary) AS subsidiary_count,
    count(DISTINCT officer) AS officer_count,
    collect(DISTINCT COALESCE(owner.name, owner.full_name))[0..5] AS owners,
    collect(DISTINCT subsidiary.name)[0..5] AS subsidiaries,
    collect(DISTINCT officer.name)[0..5] AS officers;


// ============================================================================
// QUERY 8: EXPORT QUERIES
// ============================================================================
// Purpose: Extract data for external analysis tools

// 8.1 - Export ownership network (for Gephi/NetworkX)
MATCH (owner)-[r:OWNS]->(owned:Entity)
RETURN 
    COALESCE(owner.entity_id, owner.person_id) AS source_id,
    COALESCE(owner.name, owner.full_name) AS source_name,
    labels(owner)[0] AS source_type,
    owned.entity_id AS target_id,
    owned.name AS target_name,
    r.ownership_percentage AS weight,
    r.status AS status
LIMIT 10000;


// 8.2 - Export high-risk entities
MATCH (e:Entity)
WHERE e.pagerank_score > 0.001 
   OR e.degree_centrality > 10
   OR e.community_id IS NOT NULL
OPTIONAL MATCH (e)-[:REGISTERED_IN]->(j:Jurisdiction {is_tax_haven: true})
WITH e, j
WHERE j IS NOT NULL OR e.pagerank_score > 0.01
RETURN 
    e.entity_id AS id,
    e.name AS name,
    e.jurisdiction_code AS jurisdiction,
    e.entity_type AS type,
    e.pagerank_score AS influence,
    e.degree_centrality AS connections,
    e.community_id AS community,
    j IS NOT NULL AS in_tax_haven
ORDER BY e.pagerank_score DESC
LIMIT 5000;


// ============================================================================
// PERFORMANCE PROFILING QUERIES
// ============================================================================
// Use PROFILE prefix to analyze query performance

// Profile beneficial ownership query
PROFILE
MATCH path = (p:Person)-[:OWNS*1..3]->(e:Entity {entity_id: 'TEST-ENTITY-001'})
RETURN p.full_name, length(path)
LIMIT 10;

// Explain query plan without execution
EXPLAIN
MATCH (e:Entity)-[:REGISTERED_IN]->(j:Jurisdiction {is_tax_haven: true})
WHERE e.status = 'Active'
RETURN e.name, j.name
LIMIT 100;


// ============================================================================
// ANALYSIS QUERIES COMPLETE
// ============================================================================
//
// Query Categories:
//   1. Beneficial Ownership (4 queries)
//   2. Red Flag Detection (6 queries)
//   3. Intermediary Analysis (4 queries)
//   4. Jurisdiction Risk (4 queries)
//   5. Network Patterns (4 queries)
//   6. Temporal Analysis (3 queries)
//   7. Search Utilities (3 queries)
//   8. Export Queries (2 queries)
//
// Parameter Placeholders:
//   $entityId    - Target entity identifier
//   $personId    - Target person identifier
//   $searchTerm  - Full-text search term
//   $personName  - Person name search
//
// Usage Example:
//   :param entityId => 'ENTITY-12345'
//   :param searchTerm => 'Holdings Ltd'
//
// ============================================================================
