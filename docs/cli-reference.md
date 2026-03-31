# SutraDB — CLI Reference

> Complete reference for `sutra` command-line interface.

---

## Commands

### `sutra serve`

Start the SPARQL HTTP server.

```bash
sutra serve                                # defaults: port 3030, data in ./sutra-data
sutra serve -p 8080 -d /data/mydb          # custom port and data directory
sutra serve --memory_only                   # in-memory only, no persistence
sutra serve --passcode mysecret             # require Bearer token on all requests
sutra serve --backup_interval 60            # auto-backup every 60 minutes
```

| Flag | Default | Description |
|---|---|---|
| `-p, --port` | `3030` | Port to listen on |
| `-d, --data_dir` | `./sutra-data` | Data directory for persistent `.sdb` storage |
| `--memory_only` | off | Run in-memory only (no persistence) |
| `--passcode` | none | Simple passcode auth; all requests except `/health` require `Authorization: Bearer <passcode>` |
| `--backup_interval` | `0` (disabled) | Periodic backup interval in minutes |

---

### `sutra query`

Execute a SPARQL query from the command line.

```bash
sutra query "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
sutra query -d /data/mydb "SELECT ?name WHERE { ?s :name ?name }"
```

| Argument/Flag | Default | Description |
|---|---|---|
| `query` (positional) | required | The SPARQL query string |
| `-d, --data_dir` | `./sutra-data` | Data directory |

---

### `sutra import`

Import N-Triples data from a file into the database.

```bash
sutra import data.nt                        # import from file
sutra import -                              # import from stdin
sutra import -d /data/mydb data.nt          # custom data directory
```

| Argument/Flag | Default | Description |
|---|---|---|
| `file` (positional) | required | Path to N-Triples file (use `-` for stdin) |
| `-d, --data_dir` | `./sutra-data` | Data directory |

---

### `sutra export`

Export all triples from the database.

```bash
sutra export                                # export to stdout as N-Triples
sutra export -o backup.nt                   # export to file
sutra export -f ttl -o data.ttl             # export as Turtle
```

| Flag | Default | Description |
|---|---|---|
| `-d, --data_dir` | `./sutra-data` | Data directory |
| `-o, --output` | stdout | Output file path |
| `-f, --format` | `nt` | Export format: `nt` (N-Triples) or `ttl` (Turtle) |

---

### `sutra info`

Show database statistics (triple count, term count, vector indexes, etc.).

```bash
sutra info
sutra info -d /data/mydb
```

| Flag | Default | Description |
|---|---|---|
| `-d, --data_dir` | `./sutra-data` | Data directory |

---

### `sutra health`

Database health diagnostics. Outputs a structured report covering HNSW vector indexes, pseudo-tables, and storage. Every metric includes context explaining what healthy vs unhealthy looks like.

```bash
sutra health                                # full health report
sutra health --rebuild_hnsw                 # rebuild all HNSW indexes
sutra health --refresh                      # rediscover pseudo-tables
sutra health -d /data/mydb                  # custom data directory
```

| Flag | Default | Description |
|---|---|---|
| `-d, --data_dir` | `./sutra-data` | Data directory |
| `--rebuild_hnsw` | off | Rebuild all HNSW indexes (removes tombstones, restores connectivity) |
| `--refresh` | off | Rediscover pseudo-tables from current graph data |

---

### `sutra update`

Check for updates and self-update the binary from GitHub releases.

```bash
sutra update                                # check and install update
sutra update --check                        # just check, don't install
```

| Flag | Default | Description |
|---|---|---|
| `--check` | off | Just check for updates without installing |

---

### `sutra install-agent`

Agent-first installer: generates structured config and a markdown notes file documenting the database setup. Designed for AI agents to call programmatically.

```bash
sutra install-agent mydb
sutra install-agent mydb --port 8080 --passcode secret --dimensions 768
sutra install-agent mydb --no_serve --launch_studio
```

| Argument/Flag | Default | Description |
|---|---|---|
| `name` (positional) | `sutra-db` | Database name (used for directory and notes file) |
| `--port` | `3030` | Port for the server |
| `--passcode` | none | Enable passcode authentication |
| `--dimensions` | `1024` | Vector dimensions for default embedding predicate |
| `--metric` | `cosine` | Distance metric: `cosine`, `euclidean`, `dot` |
| `--no_serve` | off | Skip server startup |
| `--launch_studio` | off | Launch Sutra Studio after setup |

---

### `sutra mcp`

Start the MCP (Model Context Protocol) server for AI agents. Runs a JSON-RPC server over stdin/stdout.

```bash
sutra mcp                                   # connect to http://localhost:3030
sutra mcp --data_dir ./mydb.sdb             # serverless mode (direct .sdb access)
sutra mcp --url http://remote:3030 --passcode secret
sutra mcp --studio                          # also launch Sutra Studio GUI
sutra mcp --no_auto_update                  # disable auto-update check
```

| Flag | Default | Description |
|---|---|---|
| `--url` | `http://localhost:3030` | SutraDB HTTP endpoint (server mode) |
| `--data_dir` | none | Data directory for serverless mode; when set, ignores `--url` |
| `--passcode` | none | Passcode for authenticated server connections |
| `--no_auto_update` | off | Disable auto-update on startup |
| `--studio` | off | Also launch Sutra Studio GUI alongside MCP |

#### MCP Tools

The MCP server exposes 12 tools via JSON-RPC:

| Tool | Description |
|---|---|
| `health_report` | Full database diagnostics (HNSW, storage, consistency) |
| `rebuild_hnsw` | Compact and rebuild all HNSW vector indexes |
| `verify_consistency` | Check SPO/POS/OSP index consistency, auto-repair |
| `database_info` | Triple count, term count, vector index count |
| `sparql_query` | Execute SPARQL+ queries |
| `insert_triples` | Insert N-Triples data |
| `backup` | Create database snapshot |
| `vector_search` | ANN search via VECTOR_SIMILAR |
| `download_studio` | Download and install Sutra Studio |
| `launch_studio` | Open Sutra Studio (downloads first if needed) |
| `check_update` | Check for new SutraDB releases |
| `decline_update` | Cancel pending auto-update |

---

## HTTP API Endpoints

When running in server mode (`sutra serve`), the following endpoints are available:

| Endpoint | Method | Description |
|---|---|---|
| `/sparql` | GET/POST | SPARQL query endpoint (standard SPARQL protocol) |
| `/triples` | POST | Insert N-Triples data |
| `/triples` | GET | Export triples (supports content negotiation) |
| `/health` | GET | Health check (always accessible, even with passcode) |
| `/info` | GET | Database statistics |
| `/vectors/search` | POST | Vector similarity search |
| `/graph` | GET/PUT/DELETE | SPARQL Graph Store Protocol |
| `/backup` | POST | Create backup snapshot |

### Content Negotiation

The `/sparql` and `/triples` endpoints support content negotiation via the `Accept` header:

| Accept Header | Format |
|---|---|
| `application/sparql-results+json` | SPARQL JSON results |
| `application/sparql-results+xml` | SPARQL XML results |
| `text/csv` | CSV |
| `text/tab-separated-values` | TSV |
| `application/n-triples` | N-Triples |
| `text/turtle` | Turtle |

### Authentication

When `--passcode` is set, all endpoints except `/health` require:

```
Authorization: Bearer <passcode>
```
