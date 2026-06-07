# CI/CD Pipeline — Orchestrix

## Pipeline Architecture

```
                      ┌──────────────────┐
                      │   Pull Request    │
                      │   (feature/*)     │
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │   PR Checks      │
                      │  pr-checks.yml   │
                      │                  │
                      │ • frontend lint  │
                      │ • frontend build │
                      │ • backend lint   │
                      │ • backend test   │
                      └────────┬─────────┘
                               │ merge
                      ┌────────▼─────────┐
                      │   Push to main   │
                      │   or develop     │
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │   CI Pipeline    │
                      │    ci.yml        │
                      │                  │
                      │ • lint + type    │
                      │ • build          │
                      │ • test + coverage│
                      │ • Docker build   │
                      └────────┬─────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼────────┐ ┌────▼────┐ ┌────────▼────────┐
     │  Staging        │ │ Weekly  │ │  Manual Deploy  │
     │  (develop)      │ │ Security│ │  deploy.yml     │
     │                 │ │ Scan    │ │                 │
     │                 │ │security │ │ staging/prod    │
     │                 │ │ .yml    │ │                 │
     └─────────────────┘ └─────────┘ └─────────────────┘
```

## Workflows

### 1. PR Checks (`pr-checks.yml`)
Triggers on every pull request to `main` or `develop`.

**Jobs (parallel):**
- `frontend-lint-typecheck` — ESLint + TypeScript type checking
- `frontend-build` — Vite production build
- `backend-lint` — Ruff lint + format check
- `backend-test` — pytest with coverage

**Gates:** All jobs must pass before merge.

### 2. CI (`ci.yml`)
Triggers on push to `main` or `develop`.

**Same jobs as PR Checks plus:**
- Docker image build verification for both frontend and backend
- Upload coverage report artifact

### 3. Security Scan (`security.yml`)
Runs weekly (Monday 6AM UTC) + manual trigger.

**Jobs (parallel):**
- `dependency-scan` — pip-audit (Python) + npm audit (frontend)
- `sast` — Bandit static analysis on backend
- `secrets-scan` — TruffleHog for leaked secrets

### 4. Deploy (`deploy.yml`)
Manual trigger via GitHub Actions UI.

**Parameters:**
- `environment`: staging or production
- `ref`: optional git ref (defaults to current branch)

**Steps:**
1. Login to GitHub Container Registry (ghcr.io)
2. Build & push backend Docker image
3. Build & push frontend Docker image
4. Placeholder deploy step — replace with your target platform

## Branch Strategy

| Branch | Environment | Purpose |
|--------|-------------|---------|
| `main` | Production | Live deployment, protected |
| `develop` | Staging | Integration testing |
| `feature/*` | — | Feature work → PR to develop |
| `fix/*` | — | Hotfix → PR to main |

## Environment Setup

### Required GitHub Secrets
| Secret | Description | Required For |
|--------|-------------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key | Tests |
| `GROQ_API_KEY` | Groq API key | Tests |
| `SUPABASE_URL` | Supabase project URL | Deploy |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | Deploy |
| `DATABASE_URL` | PostgreSQL connection string | Deploy |

### GitHub Environments
Create two environments in GitHub UI:
- `staging` — with required reviewers (optional)
- `production` — with required reviewers

## Secrets Setup

### GitHub Actions Secrets
```bash
gh secret set GEMINI_API_KEY --body "your-key"
gh secret set GROQ_API_KEY --body "your-key"
gh secret set SUPABASE_URL --body "https://[ref].supabase.co"
gh secret set SUPABASE_SERVICE_KEY --body "your-key"
gh secret set DATABASE_URL --body "postgresql://..."
```

### Environment-level Secrets (for deploy.yml)
```bash
gh secret set --env staging SUPABASE_URL "..."
gh secret set --env staging DATABASE_URL "..."
gh secret set --env production SUPABASE_URL "..."
gh secret set --env production DATABASE_URL "..."
```

## Deployment Process

### Frontend
1. `npm ci` → `npx vite build` → static files in `dist/`
2. Docker multi-stage build copies `dist/` to nginx image
3. Push to `ghcr.io`

### Backend
1. `pip install -r requirements.txt`
2. Docker build with Python 3.12-slim
3. Push to `ghcr.io`

### Adding a Real Deploy Target
Replace the placeholder in `deploy.yml` with your platform:

**Render:**
```yaml
- run: |
    curl -X POST "https://api.render.com/v1/services/${{ secrets.RENDER_SERVICE_ID }}/deploys" \
      -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}"
```

**SSH + docker-compose:**
```yaml
- run: |
    ssh deploy@host "cd /app && docker compose pull && docker compose up -d"
```

**Kubernetes:**
```yaml
- run: |
    kubectl set image deployment/backend backend=${{ steps.tags.outputs.backend_tag }}
    kubectl set image deployment/frontend frontend=${{ steps.tags.outputs.frontend_tag }}
```

## Rollback Strategy

### Image-based Rollback
Each deployment pushes tagged images:
- `ghcr.io/org/repo-backend:<sha>` — immutable
- `ghcr.io/org/repo-backend:latest` — mutable

To rollback:
```bash
docker pull ghcr.io/org/repo-backend:<previous-sha>
docker tag ghcr.io/org/repo-backend:<previous-sha> ghcr.io/org/repo-backend:latest
docker push ghcr.io/org/repo-backend:latest
# Trigger deploy
```

### Git-based Rollback
```bash
git revert <bad-deploy-sha>
git push origin main
# CI deploys the revert
```

## Local Development with Docker

```bash
# Start both services
docker compose up -d

# View logs
docker compose logs -f

# Rebuild after changes
docker compose build
docker compose up -d
```

## Cost Optimization Notes

- **Cache reuse:** npm ci (cached via `actions/setup-node`), pip (layer cached in Docker builds)
- **Concurrency:** All jobs run in parallel within each workflow
- **Cancel in-progress:** Concurrency group cancels stale runs on the same branch
- **Artifact retention:** PR artifacts kept 3 days, CI artifacts 7 days
- **No unnecessary triggers:** Paths-ignore excludes docs and config-only changes
- **Security scan weekly:** Not on every commit to reduce Actions minutes

## Troubleshooting

### Tests fail with "could not translate host name"
The test suite connects to a real Supabase instance. Tests that need PostgreSQL are skipped when `SUPABASE_URL` is not set. Set `DATABASE_URL=sqlite:///./test.db` to use SQLite in CI.

### ESLint fails with "Parsing error"
Ensure `@typescript-eslint/parser` is installed and `tsconfig.json` is valid.

### Docker build fails with "permission denied"
Ensure the GitHub Actions runner has permissions to push to the container registry. Use `GITHUB_TOKEN` for ghcr.io access.

### Security scan false positives
Add exclusions to bandit config or trufflehog config. File an issue to review.
