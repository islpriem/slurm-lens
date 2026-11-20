# slurm-lens

slurm-lens shows how a Slurm cluster is used and how its scheduler decides. A collector reads the
Slurm REST API (slurmrestd) with the token of a normal user and stores snapshots and the
accounting history in PostgreSQL, a web app turns them into statistics.

## Features

- Collector: queue, nodes, configuration and fairshare every few minutes, the accounting history
  without gaps from a start date; read-only and gentle with slurmrestd
- GPUs and nodes: allocation per model and node over time, idle capacity
- Queue: why jobs are pending, GPUs wanted per partition, waits, submissions per weekday and hour
- Jobs: sizes, backfill or main scheduler, time limits and runtimes, final states
- Users and accounts: GPU hours, fairshare, pending jobs; pseudonyms by default
- Health: collector runs, requests to slurmrestd, gaps in the history

## Deployment

On a server with Docker and access to slurmrestd:

```sh
sudo mkdir /etc/slurm-lens
sudo cp config/slurm-lens.example.ini /etc/slurm-lens/slurm-lens.ini  # set the url of slurmrestd
ssh <login-node> scontrol token lifespan=<seconds> | cut -d= -f2 | sudo install -m 600 -o 1000 /dev/stdin /etc/slurm-lens/token
echo "SLURM_LENS_DB_PASSWORD=$(openssl rand -hex 16)" > .env
docker compose up -d --build
```

The web app listens on port 8000 for a reverse proxy. Updates are `git pull && docker compose up
-d --build`, the database is migrated on start. A new token can replace the file at any time.

## Components

| Path                          |                                                              |
| ----------------------------- | ------------------------------------------------------------ |
| `src/slurm_lens/client.py`    | read-only access to slurmrestd                               |
| `src/slurm_lens/slurm.py`     | the endpoints and how their responses become rows            |
| `src/slurm_lens/collector.py` | one run and the loop                                         |
| `src/slurm_lens/models.py`    | database schema, migrations in `migrations/`                 |
| `src/slurm_lens/cli.py`       | `slurm-lens migrate`, `collect`, `status`, `serve`           |
| `src/slurm_lens/api/`         | FastAPI, one router per page that computes its charts        |
| `web/`                        | SvelteKit, shadcn-svelte and d3, draws what the API computed |

## Development

Needs Docker, [uv](https://docs.astral.sh/uv/) and Node.

```sh
cp config/slurm-lens.example.ini config/local.ini  # database host localhost, no token_file
make up                   # PostgreSQL and the web app on http://localhost:8000
make restore DUMP=<file>  # load a dump of the production database
cd web && npm install && cd .. && make web  # frontend with hot reload on http://localhost:5173
make test lint
```

The collector does not run locally by default, `make collect` does one run with the token in
`.env`.

## License

MIT
