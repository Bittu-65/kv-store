import socket
import os
import threading
import time

# --- ADDED: structured logging for LogLens ---
from kvlogger import log_event, Timer

NODE_ID = "primary-1"
ROLE = "leader"
REPLICA_TARGETS = ["replica-1"]
HEARTBEAT_INTERVAL_SEC = 2
# --- END ADDED ---

WAL_FILE = "/opt/kvstore/data/wal.log"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 5000))
server.listen(1)

storage = {}
index = {}
# connect to replica at startup
replica_conn = None
try:
    replica_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    replica_conn.connect(('127.0.0.1', 5001))
    print("Connected to replica on port 5001")
except ConnectionRefusedError:
    print("Replica not available — running without replication")
    replica_conn = None


def replay_wal():
    if not os.path.exists(WAL_FILE):
        print("No WAL file found, starting fresh")
        return
    print("Replaying WAL...")
    with open(WAL_FILE, "r") as f:
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    break

                parts = line.strip().split()
                if not parts:
                    continue

                command = parts[0]
                key = parts[1]

                if command == "SET":
                    storage[key] = parts[2]
                    index[key] = pos
                elif command == "DELETE":
                    if key in storage:
                        del storage[key]
                    index[key] = pos

    print(f"WAL replayed — {len(storage)} keys loaded, {len(index)} keys indexed")


def write_wal(key, command):
    with open(WAL_FILE, "a") as f:
        pos = f.tell()  # "a" = append, never overwrites
        f.write(command + "\n")

        index[key] = pos  # track where this command was written in the WAL

        print(f"Index updated: {key} -> byte {pos}")
    return pos  # --- ADDED: return WAL offset so callers can log it as replication_offset


def forward_to_replica(command):
    if replica_conn is None:
        return False  # --- ADDED: return success/failure so caller can log it
    try:
        replica_conn.send(command.encode() + b"\n")
        return True
    except Exception as e:
        print("Replica forwarding failed — skipping")
        # --- ADDED: log the replication failure ---
        log_event(
            event_type="error",
            node_id=NODE_ID,
            role=ROLE,
            status="error",
            error_message=f"replicate failed: {e}",
            replica_targets=REPLICA_TARGETS,
        )
        # --- END ADDED ---
        return False


def handle_command(data):
    parts = data.decode().split()
    command = parts[0].upper()

    if command == "SET":
        key, value = parts[1], parts[2]
        wal_pos = write_wal(key, f"SET {key} {value}")  # log first
        storage[key] = value  # then update dict
        replicated = forward_to_replica(f"SET {key} {len(value)}\n{value}")
        # --- ADDED: log the replicate event for a successful forward ---
        if replicated:
            log_event(
                event_type="replicate",
                node_id=NODE_ID,
                role=ROLE,
                key=key,
                value_size_bytes=len(value),
                replica_targets=REPLICA_TARGETS,
                replication_offset=wal_pos,
            )
        # --- END ADDED ---
        return b"OK"

    elif command == "GET":
        key = parts[1]
        if key in storage:
            return storage[key].encode()
        return b"None"

    elif command == "DELETE":
        key = parts[1]
        if key in storage:
            write_wal(key, f"DELETE {key}")   # log first
            del storage[key]  # then update dict
            replicated = forward_to_replica(f"DELETE {key}")
            if replicated:
                log_event(
                    event_type="replicate",
                    node_id=NODE_ID,
                    role=ROLE,
                    key=key,
                    replica_targets=REPLICA_TARGETS,
                    command="DELETE",
                )
            return b"Deleted"
        return b"Key not found"

    else:
        return b"Unknown command"


# --- ADDED: background heartbeat thread ---
def heartbeat_loop():
    while True:
        log_event(
            event_type="heartbeat",
            node_id=NODE_ID,
            role=ROLE,
        )
        time.sleep(HEARTBEAT_INTERVAL_SEC)


heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
heartbeat_thread.start()
# --- END ADDED ---

# startup — replay WAL before accepting any clients
replay_wal()
print("Server is listening on port 5000...")

while True:
    conn, address = server.accept()
    print(f"Got a connection from {address}")

    conn_file = conn.makefile('rb')  # 'rb' = read bytes

    # --- ADDED: wrap the WHOLE per-connection loop so a connection-level
    # failure (client disconnects abruptly, network reset) closes only
    # THIS connection instead of crashing the entire server process and
    # dropping every other connected client. Found via chaos testing —
    # sending malformed commands then disconnecting killed the whole
    # server before this fix.
    try:
        while True:
            # read the first line — contains command, key, and maybe byte count
            first_line = conn_file.readline()

            if not first_line:
                print(f"Client {address} disconnected")
                break

            first_line = first_line.strip().decode()
            parts = first_line.split()
            command = parts[0].upper()

            # NOTE: log_event calls that need latency_ms are placed AFTER the `with`
            # block exits, since Timer only sets elapsed_ms on __exit__ — logging
            # inside the block would always record latency_ms as None.
            try:
                key = None
                value = ""
                replicated = False
                wal_pos = None
                with Timer() as t:
                    if command == "SET":
                        key = parts[1]
                        byte_count = int(parts[2])          # how many bytes is the value?
                        value_bytes = conn_file.read(byte_count)  # read exactly that many
                        conn_file.read(1)                   # consume the trailing newline
                        value = value_bytes.decode()
                        wal_pos = write_wal(key, f"SET {key} {value}")  # log first
                        storage[key] = value             # then update dict
                        replicated = forward_to_replica(f"SET {key} {len(value)}\n{value}")
                        response = b"OK"
                    else:
                        data = first_line.encode()          # GET/DELETE stay as one line
                        response = handle_command(data)
                        key = parts[1] if len(parts) > 1 else None

                # --- logging happens here, after Timer has set t.elapsed_ms ---
                if command == "SET":
                    if replicated:
                        log_event(
                            event_type="replicate",
                            node_id=NODE_ID,
                            role=ROLE,
                            key=key,
                            value_size_bytes=len(value),
                            replica_targets=REPLICA_TARGETS,
                            replication_offset=wal_pos,
                        )
                    log_event(
                        event_type="write",
                        node_id=NODE_ID,
                        role=ROLE,
                        key=key,
                        value_size_bytes=len(value),
                        latency_ms=t.elapsed_ms,
                        command="SET",
                    )
                elif command == "GET":
                    log_event(
                        event_type="read",
                        node_id=NODE_ID,
                        role=ROLE,
                        key=key,
                        value_size_bytes=len(response) if response != b"None" else 0,
                        latency_ms=t.elapsed_ms,
                        status="ok" if response != b"None" else "error",
                        error_message=None if response != b"None" else "key not found",
                    )
                elif command == "DELETE":
                    log_event(
                        event_type="write",
                        node_id=NODE_ID,
                        role=ROLE,
                        key=key,
                        latency_ms=t.elapsed_ms,
                        command="DELETE",
                        status="ok" if response == b"Deleted" else "error",
                        error_message=None if response == b"Deleted" else "key not found",
                    )
            except Exception as e:
                log_event(
                    event_type="error",
                    node_id=NODE_ID,
                    role=ROLE,
                    status="error",
                    error_message=str(e),
                )
                response = b"ERROR"

            print(f"Command: {first_line} → Response: {response.decode()}")
            conn.send(response)

    except (ConnectionResetError, BrokenPipeError) as e:
        print(f"Client {address} connection lost: {e}")
    except Exception as e:
        print(f"Unexpected error handling client {address}: {e}")
    # --- END ADDED ---

    conn_file.close()
    conn.close()