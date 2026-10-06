# TalentHub Odoo 19 Integration

## 1. Project Overview

**TalentHub Odoo Integration** is a standalone Odoo 19 Community application that serves as a **read-only aggregate statistics viewer** for job positions evaluated in the [TalentHub / CVSystem](https://github.com/mastercake593-sudo) ASP.NET platform.

### Key Capabilities:
- **Dedicated Odoo App**: A clean `TalentHub` menu with Positions list, detailed forms, and an import wizard.
- **Secure Per-Position Import**: Integrates with TalentHub using short-lived or scoped per-position API tokens without storing tokens in the Odoo database.
- **Idempotent Data Refresh**: Re-importing updates the existing Position and refreshes its aggregate results cleanly.
- **Rich Metric Types**:
  - **Numeric Attributes** (e.g., GPA, Experience): count, average, minimum, maximum.
  - **Boolean Attributes** (e.g., Remote Work): true count, false count.
  - **Categorical / OneOfMany Attributes** (e.g., English Level): popular values breakdown (normalized relational storage in `talenthub.attribute.popular.value`).
- **Read-Only Viewer**: Acts purely as a consumer and visualization tool; it never mutates data in the core TalentHub platform.

---

## 2. Architecture & Data Flow

```text
┌────────────────────────┐
│  TalentHub ASP.NET     │
│   (CVSystem Backend)   │
└───────────┬────────────┘
            │  GET /api/integrations/odoo/position
            │  Authorization: Bearer <positionApiToken>
            ▼
┌────────────────────────┐
│  Odoo 19 Community     │
│  (talenthub_integration│
│       custom addon)    │
└───────────┬────────────┘
            │  Odoo ORM (upsert position & attributes)
            ▼
┌────────────────────────┐
│  PostgreSQL Database   │
│  (Railway / Docker)    │
└────────────────────────┘
```

1. The recruiter/interviewer copies a **Position API Token** from TalentHub for a specific position.
2. In Odoo, they click **"Import from TalentHub"** and provide the TalentHub Base URL and token.
3. Odoo calls `GET {baseUrl}/api/integrations/odoo/position`.
4. Odoo validates the response, creates or updates the `talenthub.position`, and stores all aggregate attributes.
5. The wizard redirects the user straight to the updated Position details view.

---

## 3. Local Docker Run Instructions

### Prerequisites
- Docker & Docker Compose installed.

### Quick Start
1. Clone the repository:
   ```bash
   git clone https://github.com/mastercake593-sudo/talenthub-odoo.git
   cd talenthub-odoo
   ```

2. Start the local stack:
   ```bash
   docker compose up -d
   ```

3. Open your browser at:
   ```text
   http://localhost:8069
   ```

4. On first launch, create an Odoo database:
   - **Master Password**: `admin_dev_password` (defined in `docker-compose.yml`)
   - **Database Name**: `talenthub_db` (or any name you choose)
   - **Email / Password**: your desired admin credentials
   - **Demo data**: optional (leave unchecked for clean environment)

5. Log in, navigate to **Apps**, remove the "Apps" filter from the search bar, search for `TalentHub Integration`, and click **Activate**.

---

## 4. Railway Deployment Guide

This repository is ready to deploy directly to [Railway](https://railway.app).

### Step 1: Create a PostgreSQL Service
If your Railway project does not already have a PostgreSQL service:
1. In your Railway project, click **+ New** -> **Database** -> **Add PostgreSQL**.
2. Railway automatically provisions PostgreSQL and generates standard connection environment variables (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `DATABASE_URL`).

### Step 2: Deploy this Repository
1. In the same Railway project, click **+ New** -> **GitHub Repo** -> select `mastercake593-sudo/talenthub-odoo`.
2. Railway detects the `Dockerfile` and builds the image automatically.

### Step 3: Configure Environment Variables
In the Railway settings for the Odoo service, ensure the following environment variables are present:

| Variable | Description | Example / Recommended Source |
| :--- | :--- | :--- |
| `PGHOST` / `DB_HOST` | PostgreSQL hostname | `${{Postgres.PGHOST}}` |
| `PGPORT` / `DB_PORT` | PostgreSQL port | `${{Postgres.PGPORT}}` |
| `PGUSER` / `DB_USER` | PostgreSQL username | `${{Postgres.PGUSER}}` |
| `PGPASSWORD` / `DB_PASSWORD` | PostgreSQL password | `${{Postgres.PGPASSWORD}}` |
| `PGDATABASE` / `DB_NAME` | PostgreSQL database name | `${{Postgres.PGDATABASE}}` |
| `PORT` | HTTP Port injected by Railway | Set automatically by Railway (e.g. `8069` or `8080`) |
| `ODOO_ADMIN_PASSWORD` | Master password for database creation/backups | Strong secret string (e.g. `SecretMasterKey2026!`) |

> **Note on Railway Networking**: Our custom `entrypoint.sh` automatically reads Railway's `$PORT` and binds Odoo's HTTP service to `0.0.0.0:$PORT`. It also understands Railway's `DATABASE_URL` format if passed.

### Step 4: Expose the Web Domain
1. In your Odoo service on Railway, go to **Settings** -> **Networking** -> **Generate Domain**.
2. Open the generated public URL in your browser.

---

## 5. Installing & Upgrading the Odoo Module

### Initial Installation in Odoo
1. Visit your deployed Odoo instance URL.
2. If this is a fresh database, use the database manager (`/web/database/manager`) with your `ODOO_ADMIN_PASSWORD` to create a new database.
3. Log in as an Administrator.
4. Go to **Apps**.
5. Enable **Developer Mode** (via Settings -> Developer Tools -> Activate the developer mode).
6. In the top menu of Apps, click **Update Apps List** -> click **Update**.
7. Remove the default `Apps` search filter, type `TalentHub Integration`, and click **Activate**.

### Upgrading After Git Updates
Whenever you deploy updates:
1. Go to **Apps** -> find **TalentHub Integration**.
2. Click the three dots `⋮` -> **Upgrade**.
*(Alternatively, Odoo can be run with `-u talenthub_integration` CLI flag during migrations).*

---

## 6. How to Use "Import from TalentHub"

1. In Odoo, open the **TalentHub** application from the main app switcher.
2. Click **Import from TalentHub** in the menu (or on any existing Position form, click **Re-import from TalentHub**).
3. In the wizard modal:
   - **TalentHub Base URL**: enter the root URL of your ASP.NET Core service (e.g. `https://talenthub-api.up.railway.app`).
   - **Position API Token**: paste the token for the specific position.
4. Click **Import**.
5. Odoo will fetch the aggregated statistics, save the record, and immediately open the imported Position view.

---

## 7. Expected TalentHub API Contract

The Odoo import wizard issues a request to:

```http
GET {baseUrl}/api/integrations/odoo/position
Authorization: Bearer {positionApiToken}
Accept: application/json
```

### Expected JSON Response Structure

```json
{
  "position": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Backend Developer"
  },
  "attributes": [
    {
      "id": "a1111111-e29b-41d4-a716-446655440001",
      "name": "GPA",
      "type": "Numeric",
      "aggregation": {
        "count": 10,
        "average": 4.2,
        "minimum": 3.1,
        "maximum": 4.9
      }
    },
    {
      "id": "b2222222-e29b-41d4-a716-446655440002",
      "name": "English Level",
      "type": "OneOfMany",
      "aggregation": {
        "count": 13,
        "popularValues": [
          {
            "value": "B2",
            "count": 8
          },
          {
            "value": "C1",
            "count": 5
          }
        ]
      }
    },
    {
      "id": "c3333333-e29b-41d4-a716-446655440003",
      "name": "Remote Work",
      "type": "Boolean",
      "aggregation": {
        "count": 12,
        "trueCount": 9,
        "falseCount": 3
      }
    }
  ]
}
```

### Error Responses Handled
- **401 / 403**: Displays `"Invalid or unauthorized API token."`
- **404**: Displays `"Position not found."`
- **5xx / Network / Timeout**: Displays a descriptive user-friendly error without crashing the server.
- **Partial / Missing Fields**: Handled safely with default fallback values (e.g. 0 counts, missing popular values).

---

## 8. Security Considerations

- **No Token Storage**: The Position API token is received inside a transient wizard (`models.TransientModel`) and is **never** saved into PostgreSQL or attached to the position records. Once the HTTP request completes and the transaction commits, the wizard record is discarded.
- **Log Masking**: Server logs never print raw API tokens; only a 4-character prefix mask (e.g., `pos_***`) is logged for diagnostic correlation.
- **Strict Read-Only Guarantee**: The module makes only HTTP `GET` requests to TalentHub and has no endpoints or logic capable of modifying the upstream TalentHub system.
- **No Hardcoded Secrets**: All database and admin credentials are supplied via environment variables (`ODOO_ADMIN_PASSWORD`, `PGHOST`, `PGPASSWORD`, etc.).

---

## 9. Project Structure

```text
talenthub-odoo/
├── .dockerignore
├── .gitattributes
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── Readme.md
└── addons/
    └── talenthub_integration/
        ├── __init__.py
        ├── __manifest__.py
        ├── models/
        │   ├── __init__.py
        │   ├── talenthub_position.py
        │   └── talenthub_attribute_result.py
        ├── wizard/
        │   ├── __init__.py
        │   └── import_position_wizard.py
        ├── views/
        │   ├── menus.xml
        │   ├── talenthub_position_views.xml
        │   └── import_position_wizard_views.xml
        └── security/
            └── ir.model.access.csv
```
