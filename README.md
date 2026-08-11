# Distributed Key-Value Database — Built from Scratch

A distributed key-value database engine built from scratch in Python, without using any database libraries. Built to deeply understand how cloud database infrastructure works under the hood — persistence, replication, indexing, and deployment.

## Architecture

```
Client (TCP)
     │
     ▼ port 5000
┌─────────────────────┐
│   Primary (EC2)     │  ← handles all reads + writes
│   public subnet     │
│   primary.py        │
└──────────┬──────────┘
           │ replication (port 5001)
           ▼
┌─────────────────────┐
│   Replica (EC2)     │  ← receives forwarded writes
│   private subnet    │
│   replica.py        │
└─────────────────────┘
```

Both instances run inside a custom AWS VPC (`kvstore-vpc`) with public and private subnets, locked down via security groups.

## Features

- **TCP socket server** — raw socket server handling `SET`, `GET`, `DELETE` commands
- **Custom wire protocol** — length-prefixed protocol so values with spaces work correctly (`SET city 8\nNew York\n`)
- **Write-Ahead Log (WAL)** — every write is logged to disk before being applied, so data survives crashes and restarts
- **Byte-position index** — uses `f.tell()` / `f.seek()` to track where each key lives in the WAL file, avoiding full file scans on lookup
- **Primary-replica replication** — writes are automatically forwarded from primary to replica with best-effort delivery; primary keeps serving clients if replica is temporarily unavailable
- **Deployed on AWS EC2** — primary in public subnet, replica in private subnet, both running as `systemd` services with auto-restart

## AWS Infrastructure

| Component | Detail |
|---|---|
| Region | ap-southeast-2 (Sydney) |
| VPC | Custom VPC with public + private subnets |
| Primary | EC2 t3.micro, public subnet, port 5000 |
| Replica | EC2 t3.micro, private subnet, port 5001 |
| Security groups | Primary: port 5000 + SSH from VPC; Replica: port 5001 + SSH from VPC |
| Process management | systemd services with auto-restart on both instances |

## How to Run Locally

**Start the replica first, then the primary:**

```bash
# Terminal 1 — replica
python replica.py

# Terminal 2 — primary
REPLICA_HOST=127.0.0.1 python primary.py
```

**Connect a client:**

```python
import socket
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('127.0.0.1', 5000))

# SET a value (length-prefixed protocol)
client.send(b"SET city 8\nNew York\n")
print(client.recv(1024))  # b'OK'

# GET it back
client.send(b"GET city\n")
print(client.recv(1024))  # b'New York'

# DELETE it
client.send(b"DELETE city\n")
print(client.recv(1024))  # b'Deleted'

client.close()
```

## Project Structure

```
kv-store/
├── primary.py      # Main server — handles client connections + replication
├── replica.py      # Replica server — receives forwarded writes from primary
├── bench.py        # Benchmark script for measuring throughput
└── README.md
```

## Key Concepts Learned

| What I built | Real cloud concept |
|---|---|
| WAL on disk | How RDS durability works |
| Byte-position index | DynamoDB partition keys, RDS query plans |
| Primary → replica sync | RDS Multi-AZ, read replicas |
| EC2 public/private subnet split | VPC architecture, security boundaries |
| systemd services | Production process management |
| Security group rules | AWS network access control |

## Known Limitations / Intentional Tradeoffs

- **No automatic failover** — if primary goes down, clients must manually reconnect to replica. Automatic failover requires consensus protocols (Raft, Paxos) — this is exactly why managed services like AWS RDS are valuable.
- **WAL grows indefinitely** — no compaction implemented. Real databases periodically compact the log to reclaim space.
- **Single client at a time** — no concurrency (no threading or async). Adding gevent or asyncio is a planned next step.
- **Read scaling** — all reads go to primary. Routing reads to replica is a known next step for scaling.

