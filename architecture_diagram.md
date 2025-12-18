# System Architecture - Panama Papers Neo4j Project

> **Version:** 1.0  
> **Stack:** Neo4j 5.x + FastAPI + Nginx + Docker  
> **Target:** Production-ready offshore financial network analysis platform

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DOCKER NETWORK: panama_network                          │
│                                   (bridge mode)                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│    ┌─────────────┐                                                                   │
│    │   BROWSER   │                                                                   │
│    │   (User)    │                                                                   │
│    └──────┬──────┘                                                                   │
│           │                                                                          │
│           │ HTTPS/HTTP :443/:80                                                      │
│           ▼                                                                          │
│    ┌─────────────────────────────────────────┐                                       │
│    │         NGINX REVERSE PROXY             │                                       │
│    │         (nginx:alpine)                  │                                       │
│    │                                         │                                       │
│    │  ┌───────────────────────────────────┐  │                                       │
│    │  │ Ports:                            │  │                                       │
│    │  │   80  → HTTP (redirect to 443)    │  │                                       │
│    │  │   443 → HTTPS (SSL termination)   │  │                                       │
│    │  └───────────────────────────────────┘  │                                       │
│    │                                         │                                       │
│    │  Routes:                                │                                       │
│    │    /api/*    → fastapi:8000            │                                       │
│    │    /browser  → neo4j:7474              │                                       │
│    │    /docs     → fastapi:8000/docs       │                                       │
│    │    /health   → fastapi:8000/health     │                                       │
│    └──────────────────┬──────────────────────┘                                       │
│                       │                                                              │
│         ┌─────────────┴─────────────┐                                                │
│         │                           │                                                │
│         ▼                           ▼                                                │
│    ┌─────────────────────┐    ┌─────────────────────────────────────┐                │
│    │   NEO4J BROWSER     │    │         FASTAPI APPLICATION         │                │
│    │   (Web UI)          │    │         (python:3.11-slim)          │                │
│    │                     │    │                                     │                │
│    │   Port: 7474 HTTP   │    │  ┌─────────────────────────────┐    │                │
│    │                     │    │  │ Port: 8000 (uvicorn)        │    │                │
│    └──────────┬──────────┘    │  │                             │    │                │
│               │               │  │ Endpoints:                  │    │                │
│               │               │  │   GET  /api/v1/entities     │    │                │
│               │               │  │   GET  /api/v1/persons      │    │                │
│               │               │  │   GET  /api/v1/ownership    │    │                │
│               │               │  │   POST /api/v1/search       │    │                │
│               │               │  │   GET  /api/v1/graph/{id}   │    │                │
│               │               │  │   GET  /health              │    │                │
│               │               │  │   GET  /docs (Swagger)      │    │                │
│               │               │  └─────────────────────────────┘    │                │
│               │               │                                     │                │
│               │               │  Environment Variables:             │                │
│               │               │    NEO4J_URI=bolt://neo4j:7687     │                │
│               │               │    NEO4J_USER=${NEO4J_USER}        │                │
│               │               │    NEO4J_PASSWORD=${NEO4J_PASS}    │                │
│               │               │    API_SECRET_KEY=${SECRET}        │                │
│               │               │    CORS_ORIGINS=["..."]            │                │
│               │               └──────────────────┬──────────────────┘                │
│               │                                  │                                   │
│               │                                  │ Bolt Protocol                     │
│               │                                  │ (encrypted, port 7687)            │
│               │                                  │                                   │
│               │               ┌──────────────────▼──────────────────┐                │
│               │               │                                     │                │
│               └───────────────▶     NEO4J 5.x DATABASE              │                │
│                               │     (neo4j:5-enterprise)            │                │
│                               │                                     │                │
│                               │  ┌─────────────────────────────┐    │                │
│                               │  │ Ports:                      │    │                │
│                               │  │   7687 → Bolt (driver)      │    │                │
│                               │  │   7474 → HTTP (browser)     │    │                │
│                               │  │   7473 → HTTPS (browser)    │    │                │
│                               │  └─────────────────────────────┘    │                │
│                               │                                     │                │
│                               │  Environment Variables:             │                │
│                               │    NEO4J_AUTH=${USER}/${PASS}      │                │
│                               │    NEO4J_PLUGINS=["apoc","gds"]    │                │
│                               │    NEO4J_dbms_memory_heap_max=2G   │                │
│                               │    NEO4J_dbms_security_auth=true   │                │
│                               │                                     │                │
│                               │  Volumes:                           │                │
│                               │    neo4j_data    → /data           │                │
│                               │    neo4j_logs    → /logs           │                │
│                               │    neo4j_import  → /var/lib/.../   │                │
│                               │    neo4j_plugins → /plugins        │                │
│                               └─────────────────────────────────────┘                │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Data Flow Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                              REQUEST/RESPONSE FLOW                                  │
└────────────────────────────────────────────────────────────────────────────────────┘

    USER                    NGINX                   FASTAPI                 NEO4J
     │                        │                        │                      │
     │  1. HTTP Request       │                        │                      │
     │  GET /api/v1/entities  │                        │                      │
     │  Authorization: Bearer │                        │                      │
     │ ──────────────────────>│                        │                      │
     │                        │                        │                      │
     │                        │  2. Proxy Request      │                      │
     │                        │  X-Real-IP: client     │                      │
     │                        │  X-Forwarded-For       │                      │
     │                        │ ──────────────────────>│                      │
     │                        │                        │                      │
     │                        │                        │  3. Validate JWT     │
     │                        │                        │  (decode & verify)   │
     │                        │                        │─────┐                │
     │                        │                        │     │                │
     │                        │                        │<────┘                │
     │                        │                        │                      │
     │                        │                        │  4. Bolt Connection  │
     │                        │                        │  (neo4j-driver)      │
     │                        │                        │                      │
     │                        │                        │  MATCH (e:Entity)    │
     │                        │                        │  WHERE e.status =    │
     │                        │                        │    'Active'          │
     │                        │                        │  RETURN e LIMIT 100  │
     │                        │                        │ ────────────────────>│
     │                        │                        │                      │
     │                        │                        │  5. Execute Query    │
     │                        │                        │                      │
     │                        │                        │  6. Return Records   │
     │                        │                        │<─────────────────────│
     │                        │                        │                      │
     │                        │                        │  7. Transform to     │
     │                        │                        │  Pydantic Models     │
     │                        │                        │─────┐                │
     │                        │                        │     │                │
     │                        │                        │<────┘                │
     │                        │                        │                      │
     │                        │  8. JSON Response      │                      │
     │                        │  Content-Type: json    │                      │
     │                        │<───────────────────────│                      │
     │                        │                        │                      │
     │  9. Response to User   │                        │                      │
     │  200 OK + JSON body    │                        │                      │
     │<───────────────────────│                        │                      │
     │                        │                        │                      │


┌────────────────────────────────────────────────────────────────────────────────────┐
│                           AUTHENTICATION FLOW (JWT)                                 │
└────────────────────────────────────────────────────────────────────────────────────┘

    USER                    NGINX                   FASTAPI                 NEO4J
     │                        │                        │                      │
     │  1. POST /api/v1/auth/login                     │                      │
     │  {"username": "analyst", "password": "..."}    │                      │
     │ ──────────────────────────────────────────────>│                      │
     │                        │                        │                      │
     │                        │                        │  2. Verify user      │
     │                        │                        │  (check password     │
     │                        │                        │   hash in DB or      │
     │                        │                        │   external IdP)      │
     │                        │                        │─────┐                │
     │                        │                        │     │                │
     │                        │                        │<────┘                │
     │                        │                        │                      │
     │                        │                        │  3. Generate JWT     │
     │                        │                        │  {sub: "analyst",    │
     │                        │                        │   role: "viewer",    │
     │                        │                        │   exp: timestamp}    │
     │                        │                        │─────┐                │
     │                        │                        │     │                │
     │                        │                        │<────┘                │
     │                        │                        │                      │
     │  4. Return JWT Token                            │                      │
     │  {"access_token": "eyJ...", "token_type": "bearer"}                   │
     │<───────────────────────────────────────────────│                      │
     │                        │                        │                      │
     │                        │                        │                      │
     │  5. Subsequent Requests with Bearer Token       │                      │
     │  Authorization: Bearer eyJ...                   │                      │
     │ ──────────────────────────────────────────────>│                      │
     │                        │                        │                      │
     │                        │                        │  6. Validate JWT     │
     │                        │                        │  - Check signature   │
     │                        │                        │  - Check expiration  │
     │                        │                        │  - Extract claims    │
     │                        │                        │─────┐                │
     │                        │                        │     │                │
     │                        │                        │<────┘                │
     │                        │                        │                      │
     │                        │                        │  7. Check RBAC       │
     │                        │                        │  (role permissions)  │
     │                        │                        │─────┐                │
     │                        │                        │     │                │
     │                        │                        │<────┘                │
     │                        │                        │                      │
     │                        │                        │  8. Process Request  │
     │                        │                        │  (if authorized)     │
     │                        │                        │                      │
```

---

## Component Descriptions

### Neo4j Database Service

| Attribute          | Value                                                            |
| ------------------ | ---------------------------------------------------------------- |
| **Image**          | `neo4j:5-enterprise` (or `neo4j:5-community` for non-commercial) |
| **Container Name** | `panama-neo4j`                                                   |
| **Hostname**       | `neo4j` (internal DNS)                                           |
| **Restart Policy** | `unless-stopped`                                                 |

**Ports:**
| Port | Protocol | Purpose |
|------|----------|---------|
| 7687 | Bolt (TCP) | Driver connections (encrypted) |
| 7474 | HTTP | Neo4j Browser web UI |
| 7473 | HTTPS | Neo4j Browser (SSL) |

**Environment Variables:**

```bash
NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}          # Initial admin credentials
NEO4J_PLUGINS=["apoc", "graph-data-science"] # Auto-install plugins
NEO4J_dbms_memory_heap_initial__size=1G      # JVM heap min
NEO4J_dbms_memory_heap_max__size=2G          # JVM heap max
NEO4J_dbms_memory_pagecache_size=1G          # Page cache for graphs
NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.*
NEO4J_dbms_security_procedures_allowlist=apoc.*,gds.*
NEO4J_dbms_connector_bolt_listen__address=0.0.0.0:7687
NEO4J_dbms_connector_http_listen__address=0.0.0.0:7474
```

**Volumes:**
| Volume Name | Mount Point | Purpose |
|-------------|-------------|---------|
| `neo4j_data` | `/data` | Database files (persistent) |
| `neo4j_logs` | `/logs` | Query & debug logs |
| `neo4j_import` | `/var/lib/neo4j/import` | CSV import directory |
| `neo4j_plugins` | `/plugins` | Custom plugins (APOC, GDS) |

**Health Check:**

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:7474"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 60s
```

---

### FastAPI Application Service

| Attribute             | Value                    |
| --------------------- | ------------------------ |
| **Base Image**        | `python:3.11-slim`       |
| **Container Name**    | `panama-api`             |
| **Hostname**          | `fastapi` (internal DNS) |
| **Restart Policy**    | `unless-stopped`         |
| **Working Directory** | `/app`                   |

**Port:**
| Port | Protocol | Purpose |
|------|----------|---------|
| 8000 | HTTP | Uvicorn ASGI server |

**Environment Variables:**

```bash
# Neo4j Connection
NEO4J_URI=bolt://neo4j:7687              # Internal Docker DNS
NEO4J_USER=neo4j                          # Database user
NEO4J_PASSWORD=${NEO4J_PASSWORD}          # From .env file
NEO4J_DATABASE=neo4j                      # Target database

# Application Settings
API_SECRET_KEY=${API_SECRET_KEY}          # JWT signing key (256-bit)
API_ALGORITHM=HS256                       # JWT algorithm
ACCESS_TOKEN_EXPIRE_MINUTES=30            # Token TTL
ENVIRONMENT=production                    # prod/staging/dev

# CORS Configuration
CORS_ORIGINS=["https://yourdomain.com"]   # Allowed origins
CORS_ALLOW_CREDENTIALS=true

# Logging
LOG_LEVEL=INFO                            # DEBUG in development
LOG_FORMAT=json                           # Structured logging
```

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key Dependencies (requirements.txt):**

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
neo4j==5.17.0
pydantic==2.5.3
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
httpx==0.26.0
structlog==24.1.0
```

**Health Check Endpoint:**

```python
@app.get("/health")
async def health_check(db: Neo4jDriver = Depends(get_db)):
    try:
        await db.verify_connectivity()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
```

---

### Nginx Reverse Proxy (Optional)

| Attribute          | Value            |
| ------------------ | ---------------- |
| **Image**          | `nginx:alpine`   |
| **Container Name** | `panama-nginx`   |
| **Hostname**       | `nginx`          |
| **Restart Policy** | `unless-stopped` |

**Ports:**
| Port | Protocol | Purpose |
|------|----------|---------|
| 80 | HTTP | Redirect to HTTPS |
| 443 | HTTPS | SSL termination |

**Nginx Configuration (`nginx.conf`):**

```nginx
upstream fastapi_backend {
    server fastapi:8000;
    keepalive 32;
}

upstream neo4j_browser {
    server neo4j:7474;
}

server {
    listen 80;
    server_name panama.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name panama.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    # API Routes → FastAPI
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://fastapi_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # Timeouts for long queries
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # Swagger Docs
    location /docs {
        proxy_pass http://fastapi_backend/docs;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /openapi.json {
        proxy_pass http://fastapi_backend/openapi.json;
    }

    # Neo4j Browser (restricted access)
    location /browser {
        # IP whitelist for admin access
        allow 10.0.0.0/8;
        allow 192.168.0.0/16;
        deny all;

        proxy_pass http://neo4j_browser;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # Health check endpoint (no auth)
    location /health {
        proxy_pass http://fastapi_backend/health;
    }
}
```

**Volumes:**
| Volume/Bind | Mount Point | Purpose |
|-------------|-------------|---------|
| `./nginx/nginx.conf` | `/etc/nginx/nginx.conf` | Main config |
| `./nginx/ssl/` | `/etc/nginx/ssl/` | SSL certificates |
| `nginx_logs` | `/var/log/nginx` | Access & error logs |

---

## Docker Compose Configuration

```yaml
version: "3.8"

services:
  # ============================================
  # NEO4J DATABASE
  # ============================================
  neo4j:
    image: neo4j:5-enterprise
    container_name: panama-neo4j
    hostname: neo4j
    restart: unless-stopped
    ports:
      - "7474:7474" # HTTP Browser (dev only, remove in prod)
      - "7687:7687" # Bolt protocol
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
      - NEO4J_dbms_memory_heap_initial__size=1G
      - NEO4J_dbms_memory_heap_max__size=2G
      - NEO4J_dbms_memory_pagecache_size=1G
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.*
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes # Enterprise only
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - neo4j_import:/var/lib/neo4j/import
      - neo4j_plugins:/plugins
    networks:
      - panama_network
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:7474 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  # ============================================
  # FASTAPI APPLICATION
  # ============================================
  fastapi:
    build:
      context: ./api
      dockerfile: Dockerfile
    container_name: panama-api
    hostname: fastapi
    restart: unless-stopped
    ports:
      - "8000:8000" # Exposed for dev, use nginx in prod
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - NEO4J_DATABASE=neo4j
      - API_SECRET_KEY=${API_SECRET_KEY}
      - API_ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=30
      - ENVIRONMENT=${ENVIRONMENT:-production}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - CORS_ORIGINS=${CORS_ORIGINS:-["http://localhost:3000"]}
    volumes:
      - ./api/app:/app/app:ro # Read-only in production
    networks:
      - panama_network
    depends_on:
      neo4j:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  # ============================================
  # NGINX REVERSE PROXY (Optional)
  # ============================================
  nginx:
    image: nginx:alpine
    container_name: panama-nginx
    hostname: nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - nginx_logs:/var/log/nginx
    networks:
      - panama_network
    depends_on:
      fastapi:
        condition: service_healthy
    profiles:
      - production # Only start with: docker compose --profile production up

# ============================================
# NETWORKS
# ============================================
networks:
  panama_network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16

# ============================================
# VOLUMES
# ============================================
volumes:
  neo4j_data:
    driver: local
  neo4j_logs:
    driver: local
  neo4j_import:
    driver: local
  neo4j_plugins:
    driver: local
  nginx_logs:
    driver: local
```

---

## Environment Variables File (`.env`)

```bash
# ===========================================
# PANAMA PAPERS ANALYSIS PLATFORM
# Environment Configuration
# ===========================================

# ---- Neo4j Database ----
NEO4J_PASSWORD=Ch@ng3M3!Str0ngP@ssw0rd2024
NEO4J_DATABASE=neo4j

# ---- FastAPI Application ----
# Generate with: openssl rand -hex 32
API_SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
API_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ---- Environment ----
ENVIRONMENT=production
LOG_LEVEL=INFO

# ---- CORS ----
CORS_ORIGINS=["https://panama.yourdomain.com","http://localhost:3000"]

# ---- SSL (production) ----
SSL_CERT_PATH=/etc/nginx/ssl/fullchain.pem
SSL_KEY_PATH=/etc/nginx/ssl/privkey.pem
```

> ⚠️ **CRITICAL:** Never commit `.env` to version control. Add to `.gitignore`.

---

## Security Considerations

### 1. Authentication & Authorization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AUTHENTICATION ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    Users     │    │   Roles      │    │ Permissions  │    │  Resources   │
├──────────────┤    ├──────────────┤    ├──────────────┤    ├──────────────┤
│ analyst_1    │───▶│ viewer       │───▶│ read:entity  │───▶│ /api/entities│
│ analyst_2    │    │              │    │ read:person  │    │ /api/persons │
│ admin_1      │───▶│ analyst      │───▶│ read:*       │    │ /api/search  │
│ service_acct │    │              │    │ write:notes  │    │              │
│              │───▶│ admin        │───▶│ read:*       │    │ /api/admin/* │
│              │    │              │    │ write:*      │    │ /browser     │
│              │───▶│ service      │───▶│ bulk:import  │    │ /api/import  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

**JWT Token Structure:**

```json
{
  "sub": "analyst_1",
  "role": "analyst",
  "permissions": [
    "read:entity",
    "read:person",
    "read:ownership",
    "write:notes"
  ],
  "exp": 1706745600,
  "iat": 1706744000,
  "jti": "unique-token-id-for-revocation"
}
```

**Role-Based Access Control (RBAC):**

| Role      | Permissions                                      | Use Case              |
| --------- | ------------------------------------------------ | --------------------- |
| `viewer`  | `read:entity`, `read:person`, `read:search`      | Read-only analysts    |
| `analyst` | All `viewer` + `write:notes`, `export:data`      | Investigation team    |
| `admin`   | All `analyst` + `manage:users`, `access:browser` | System administrators |
| `service` | `bulk:import`, `bulk:export`                     | ETL pipelines         |

### 2. Network Security

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NETWORK SECURITY LAYERS                            │
└─────────────────────────────────────────────────────────────────────────────┘

    INTERNET                    DMZ                      INTERNAL
        │                        │                          │
        │    ┌───────────────────┴───────────────────┐      │
        │    │           FIREWALL / WAF              │      │
        │    │  - Rate limiting (100 req/min)        │      │
        │    │  - IP blacklisting                    │      │
        │    │  - SQL injection prevention           │      │
        │    │  - DDoS protection                    │      │
        │    └───────────────────┬───────────────────┘      │
        │                        │                          │
        │              ┌─────────▼─────────┐                │
        │              │      NGINX        │                │
        │              │  (SSL termination)│                │
        │              │  Port 443 only    │                │
        │              └─────────┬─────────┘                │
        │                        │                          │
        │    ════════════════════╪══════════════════════    │
        │         Docker Network │ (172.28.0.0/16)          │
        │    ════════════════════╪══════════════════════    │
        │                        │                          │
        │              ┌─────────▼─────────┐                │
        │              │     FastAPI       │                │
        │              │  (no external IP) │                │
        │              └─────────┬─────────┘                │
        │                        │                          │
        │              ┌─────────▼─────────┐                │
        │              │      Neo4j        │                │
        │              │  (no external IP) │                │
        │              │  Bolt: encrypted  │                │
        │              └───────────────────┘                │
```

### 3. Credential Management

| Secret           | Storage Method         | Rotation Period         |
| ---------------- | ---------------------- | ----------------------- |
| `NEO4J_PASSWORD` | Docker secrets / Vault | 90 days                 |
| `API_SECRET_KEY` | Docker secrets / Vault | 30 days                 |
| SSL certificates | Certbot auto-renewal   | 90 days (Let's Encrypt) |
| JWT tokens       | Short-lived (30 min)   | Per session             |

### 4. Input Validation (Pydantic Models)

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
import re

class EntitySearchRequest(BaseModel):
    """Validated search request - prevents injection attacks."""

    query: str = Field(..., min_length=2, max_length=200)
    jurisdiction: Optional[str] = Field(None, regex=r'^[A-Z]{2,3}$')
    entity_type: Optional[str] = Field(None)
    limit: int = Field(default=50, ge=1, le=500)
    skip: int = Field(default=0, ge=0)

    @validator('query')
    def sanitize_query(cls, v):
        # Remove potential Cypher injection patterns
        dangerous_patterns = [
            r'MATCH\s*\(',
            r'CREATE\s*\(',
            r'DELETE\s+',
            r'DETACH\s+',
            r'CALL\s+\{',
            r'\/\*.*\*\/',
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError('Invalid characters in search query')
        return v.strip()

    @validator('entity_type')
    def validate_entity_type(cls, v):
        allowed = {'Company', 'Trust', 'Fund', 'Foundation', 'Partnership'}
        if v and v not in allowed:
            raise ValueError(f'entity_type must be one of: {allowed}')
        return v
```

### 5. Neo4j Security Configuration

```cypher
// Create application-specific database user (principle of least privilege)
CREATE USER api_user SET PASSWORD 'secure_password' CHANGE NOT REQUIRED;
GRANT ROLE reader TO api_user;

// Custom role with limited write access
CREATE ROLE analyst;
GRANT MATCH {*} ON GRAPH neo4j TO analyst;
GRANT WRITE ON GRAPH neo4j NODE Note TO analyst;
DENY DELETE ON GRAPH neo4j TO analyst;
DENY WRITE ON GRAPH neo4j RELATIONSHIP OWNS TO analyst;

// Rate limiting via APOC (application level)
CALL apoc.config.map('apoc.max.degreeCentrality.batch', 1000);
```

---

## Startup Commands

**Development:**

```bash
# Start without nginx
docker compose up -d neo4j fastapi

# View logs
docker compose logs -f fastapi

# Access Neo4j Browser
open http://localhost:7474
```

**Production:**

```bash
# Start all services including nginx
docker compose --profile production up -d

# Verify health
curl -s https://panama.yourdomain.com/health | jq

# Scale API if needed
docker compose up -d --scale fastapi=3
```

**Data Import:**

```bash
# Copy CSV files to import volume
docker cp ./data/entities.csv panama-neo4j:/var/lib/neo4j/import/

# Run import inside container
docker exec -it panama-neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  "LOAD CSV WITH HEADERS FROM 'file:///entities.csv' AS row
   CREATE (e:Entity {entity_id: row.id, name: row.name})"
```

---

## Monitoring & Observability

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MONITORING STACK (Optional)                          │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │   Grafana       │ ◄─── Dashboards & Alerts
                    │   :3000         │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │   Prometheus    │           │     Loki        │
    │   :9090         │           │   :3100         │
    │   (metrics)     │           │   (logs)        │
    └────────┬────────┘           └────────┬────────┘
             │                             │
    ┌────────┴─────────────────────────────┴────────┐
    │                                               │
    ▼                   ▼                   ▼       ▼
┌───────┐         ┌─────────┐         ┌───────┐  Promtail
│Neo4j  │         │FastAPI  │         │Nginx  │  (log collector)
│metrics│         │metrics  │         │logs   │
│:2004  │         │:8000    │         │       │
└───────┘         └─────────┘         └───────┘
```

**Key Metrics to Monitor:**

| Service | Metric                              | Alert Threshold |
| ------- | ----------------------------------- | --------------- |
| Neo4j   | `neo4j_bolt_connections_active`     | > 100           |
| Neo4j   | `neo4j_page_cache_hit_ratio`        | < 0.95          |
| Neo4j   | `neo4j_transaction_active`          | > 50            |
| FastAPI | `http_request_duration_seconds`     | p99 > 2s        |
| FastAPI | `http_requests_total{status="5xx"}` | > 10/min        |
| Nginx   | `nginx_http_requests_total`         | > 1000/min      |

---

_Architecture designed for ICIJ Panama Papers analysis. Suitable for production deployment with appropriate security hardening._
