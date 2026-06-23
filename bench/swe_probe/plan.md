# Plan — pallets__flask-5063

**File:** `src/flask/cli.py`, function `routes_command` (the `flask routes` CLI).

**Goal:** show which subdomain (or host) each route is registered under, so
`flask routes` is useful for apps that use `SERVER_NAME` subdomains or
host matching.

**Changes (this function + its imports/options):**
1. Detect domain mode: `host_matching = current_app.url_map.host_matching`,
   and `has_domain = any(rule.host if host_matching else rule.subdomain
   for rule in rules)`. Only add the domain column when `has_domain` is true.
2. The domain column value per rule is `rule.host` when host_matching else
   `rule.subdomain`, falling back to `""`. Column header is `"Host"` when
   host_matching else `"Subdomain"`.
3. Add `"domain"` to the `--sort` choices and allow sorting by the domain
   column. Build the table as a list of rows (each a list of cells), sort
   rows by the chosen column index, fall back to no sort if the sort name
   isn't a column.
4. Keep the existing aligned-table rendering: a header row, a dashes
   separator row, columns left-justified and padded to the widest cell,
   joined by two spaces.

Don't change other functions. Preserve existing columns (Endpoint, Methods,
Rule) and default sort (endpoint).
