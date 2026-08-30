# n8n

This folder holds **sample files** (`samples/`) used with n8n workflows.

The **n8n app itself** runs in Docker. Workflows and login data live in the Docker volume `n8n_data` (not in this folder).

**UI:** [http://localhost:5678](http://localhost:5678)

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) running
- Image: `docker.n8n.io/n8nio/n8n:latest`
- Volume: `n8n_data` (created on first install)

---

## Basic commands

### Start (existing container)

```bash
docker start n8n
```

Then open [http://localhost:5678](http://localhost:5678).

### Stop

```bash
docker stop n8n
```

### Restart

```bash
docker restart n8n
```

### Status

```bash
docker ps --filter name=n8n
```

### Logs

```bash
docker logs n8n
docker logs -f n8n          # follow live
docker logs --tail 50 n8n   # last 50 lines
```

### Open the UI

```bash
# Windows (Git Bash / MINGW64)
start http://localhost:5678

# or just open in browser:
# http://localhost:5678
```

---

## First-time / recreate container

If the `n8n` container was removed but the volume still exists (your data is safe):

```bash
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n:latest
```

If the name is already taken:

```bash
docker rm -f n8n
# then run the docker run command above again
```

---

## Pull latest image

```bash
docker pull docker.n8n.io/n8nio/n8n:latest
docker stop n8n
docker rm n8n
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n:latest
```

---

## Data & volumes

| Item | Purpose |
|------|---------|
| Volume `n8n_data` | Workflows, credentials, settings |
| Container `n8n` | Running process (safe to remove/recreate) |
| This folder `n8n/samples/` | Sample PDFs for workflows — not the app |

List the volume:

```bash
docker volume ls | grep n8n
docker volume inspect n8n_data
```

**Do not** delete `n8n_data` unless you want to wipe all workflows:

```bash
# DESTRUCTIVE — deletes all n8n data
# docker volume rm n8n_data
```

---

## Why `curl … get.n8n.io` fails here

```text
Error: ./n8n exists and is not empty — refusing to write into it.
```

This repo already has an `n8n/` folder (samples). The installer wants an empty `./n8n` directory.

To install the Docker helper scripts elsewhere instead:

```bash
curl -fsSL https://get.n8n.io -o get-n8n.sh
N8N_DIR=./n8n-docker sh get-n8n.sh
```

You usually don’t need that — use the Docker commands above with the existing `n8n_data` volume.

---

## Samples

```text
n8n/
├── README.md          ← this file
└── samples/
    └── fictional-leads/   # sample PDFs / scripts for lead workflows
```

---

## Quick reference

| Action | Command |
|--------|---------|
| Start | `docker start n8n` |
| Stop | `docker stop n8n` |
| Restart | `docker restart n8n` |
| Logs | `docker logs -f n8n` |
| Status | `docker ps --filter name=n8n` |
| UI | http://localhost:5678 |
