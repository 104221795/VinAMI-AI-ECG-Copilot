# Local Development

Requirements: Node 20+, pnpm 10.34.5, Python 3.12 for backend work and Docker Compose for the integrated stack.

```bash
pnpm install --frozen-lockfile
docker compose up -d postgres redis migrate api worker
pnpm dev
```

Open `http://localhost:3000`. API documentation is at `http://localhost:8000/docs`; Prometheus is at `http://localhost:9090`.

For integrated validation:

```bash
docker compose up --build
docker compose exec -T api python -m scripts.seed
```

Configuration is documented in `.env.example`. `VINAMI_API_BASE_URL` is server-only. Variables beginning with `NEXT_PUBLIC_` contain display branding only and must never contain credentials. Development identity accepts predefined fixtures only.
