# slurm-lens

slurm-lens collects how a Slurm cluster is used and how its scheduler decides, to explain later
why jobs wait and who uses which resources. It reads the Slurm REST API (slurmrestd) with the
token of a normal user and stores everything in PostgreSQL.

## Features

- Snapshots of the queue, the nodes and the fairshare tree every few minutes
- Configuration (partitions, nodes, QOS, ...) with its history of changes
- The accounting history in fixed windows, without gaps from a start date
- Read-only and gentle with slurmrestd: only allowed GET requests, pauses and retries
- `slurm-lens status` shows what was collected, also as health check of the container

## Deployment

On a server with Docker and access to slurmrestd:

```sh
sudo mkdir /etc/slurm-lens
sudo cp config/slurm-lens.example.ini /etc/slurm-lens/slurm-lens.ini  # set the url of slurmrestd
ssh <login-node> scontrol token lifespan=<seconds> | cut -d= -f2 | sudo install -m 600 -o 1000 /dev/stdin /etc/slurm-lens/token
echo "SLURM_LENS_DB_PASSWORD=$(openssl rand -hex 16)" > .env
docker compose up -d --build
```

Updates are `git pull && docker compose up -d --build`, the database is migrated on start. A new
token can replace the file at any time.

## Components

| Path                          |                                                   |
| ----------------------------- | ------------------------------------------------- |
| `src/slurm_lens/client.py`    | read-only access to slurmrestd                    |
| `src/slurm_lens/slurm.py`     | the endpoints and how their responses become rows |
| `src/slurm_lens/collector.py` | one run and the loop                              |
| `src/slurm_lens/models.py`    | database schema, migrations in `migrations/`      |
| `src/slurm_lens/cli.py`       | `slurm-lens migrate`, `collect`, `status`         |

## Development

Needs Docker and [uv](https://docs.astral.sh/uv/).

```sh
ssh <login-node> scontrol token lifespan=36000 > .env
cp config/slurm-lens.example.ini config/local.ini  # database host localhost, no token_file
make up      # PostgreSQL and the collector
make status  # what was collected so far
make test lint
```
