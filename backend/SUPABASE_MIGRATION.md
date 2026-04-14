# Supabase PostgreSQL Migration Guide

This guide will help you migrate from SQLite to Supabase PostgreSQL.

## Prerequisites

1. A Supabase account at [supabase.com](https://supabase.com)
2. Create a new project or use an existing one

## Step 1: Get Your Supabase Database Credentials

1. Go to your Supabase project dashboard
2. Navigate to **Settings** > **Database**
3. Scroll down to **Connection Pooling** section
4. Copy the **URI** format:
   ```
   postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
   ```

## Step 2: Update Your .env File

Add your Supabase credentials to the `.env` file:

```bash
# Disable SQLite
DATABASE_URL=

# Enable Supabase PostgreSQL
SUPABASE_DB_URL=postgresql://postgres.[PROJECT_REF]:[YOUR_PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

Or directly set the DATABASE_URL:

```bash
DATABASE_URL=postgresql://postgres.[YOUR_PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
```

## Step 3: Migrate Existing Data

### Option A: Using the Migration Script

```bash
cd backend
source venv/bin/activate

# Run the migration script (creates tables in Supabase)
python migrate_to_supabase.py
```

### Option B: Export/Import

1. **Export from SQLite:**
   ```bash
   sqlite3 orchestrix.db ".dump" > backup.sql
   ```

2. **Import to Supabase:**
   - Go to Supabase Dashboard > SQL Editor
   - Run your backup.sql

## Step 4: Verify Connection

```bash
cd backend
source venv/bin/activate
python3 -c "from database import is_postgres; print(f'PostgreSQL mode: {is_postgres()}')"
```

## Connection String Formats

### Supabase Connection Pooling (Recommended for serverless)
```
postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

### Direct Connection (For local development)
```
postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/[DBNAME]
```

### Environment Variable Examples

```bash
# Supabase Connection Pooler
SUPABASE_DB_URL=postgresql://postgres.xyz123:your_password@aws-0-us-east-1.pooler.supabase.com:6543/postgres

# Direct connection (from Supabase settings)
DATABASE_URL=postgresql://postgres:your_password@db.xyz123.supabase.co:5432/postgres
```

## Troubleshooting

### Connection Refused
- Check if your IP is whitelisted in Supabase (Settings > Database > Connection Pooling > Allowed IPs)
- For development, set **Connection Pooling > SSL Mode** to `Require` or `Disable`

### Authentication Failed
- Double-check your password (special characters may need URL encoding)
- Ensure the password matches what's in Supabase

### Pool Timeout
- Reduce `pool_size` in database.py if experiencing connection limits
- Consider using connection pooling for serverless functions

## Environment Variables Summary

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Direct PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `SUPABASE_DB_URL` | Supabase connection pooler URL | `postgresql://postgres.ref:pass@pooler.supabase.com:6543/postgres` |
| `USE_ASYNC` | Enable async driver (default: false) | `true` or `false` |

## Production Checklist

- [ ] Use strong passwords
- [ ] Enable SSL connections
- [ ] Set up connection pooling for serverless
- [ ] Configure connection timeouts
- [ ] Set up database backups
- [ ] Monitor query performance
