import socket
import os

WAL_FILE = "/opt/kvstore/data/replica_wal.log"  # separate WAL from primary's

storage = {}
index = {}

def replay_wal():
    if not os.path.exists(WAL_FILE):
        print("Replica: no WAL found, starting fresh")
        return
    print("Replica: replaying WAL...")
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
    print(f"Replica: {len(storage)} keys loaded")

def write_wal(key, command):
    with open(WAL_FILE, "a") as f:
        pos = f.tell()
        f.write(command + "\n")
        index[key] = pos

replica = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
replica.bind(('0.0.0.0', 5001))  # listen on all network interfaces
replica.listen(1)

replay_wal()
print("Replica listening on port 5001...")

while True:
    conn, address = replica.accept()
    print(f"Replica: primary connected from {address}")
    
    conn_file = conn.makefile('rb')
    
    while True:
        first_line = conn_file.readline()
        if not first_line:
            print("Replica: primary disconnected")
            break
        
        first_line = first_line.strip().decode()
        parts = first_line.split()
        command = parts[0].upper()
        
        if command == "SET":
            key = parts[1]
            byte_count = int(parts[2])
            value_bytes = conn_file.read(byte_count)
            conn_file.read(1)
            value = value_bytes.decode()
            write_wal(key, f"SET {key} {value}")
            storage[key] = value
            print(f"Replica: SET {key} = {value}")
        
        elif command == "DELETE":
            key = parts[1]
            if key in storage:
                write_wal(key, f"DELETE {key}")
                del storage[key]
            print(f"Replica: DELETE {key}")
    
    conn.close()