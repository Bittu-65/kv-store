import argparse
import os
import socket
import time

PRIMARY_ADDR = ('127.0.0.1', 5000)
REPLICA_WAL = os.path.normpath(os.path.join(os.sep, 'opt', 'kvstore', 'data', 'replica_wal.log'))


def make_client():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(PRIMARY_ADDR)
    return client


def bench_writes(n=1000):
    client = make_client()
    start = time.perf_counter()
    for i in range(n):
        value = f"value{i}"
        msg = f"SET key{i} {len(value)}\n{value}\n".encode()
        client.sendall(msg)
        client.recv(1024)
    elapsed = time.perf_counter() - start
    client.close()
    print(f"Writes: {n} ops in {elapsed:.2f}s = {n / elapsed:.0f} ops/sec")
    return elapsed


def bench_reads(n=1000):
    client = make_client()
    for i in range(100):
        value = f"value{i}"
        msg = f"SET key{i} {len(value)}\n{value}\n".encode()
        client.sendall(msg)
        client.recv(1024)
    client.close()

    client = make_client()
    start = time.perf_counter()
    for i in range(n):
        msg = f"GET key{i % 100}\n".encode()
        client.sendall(msg)
        client.recv(1024)
    elapsed = time.perf_counter() - start
    client.close()
    print(f"Reads: {n} ops in {elapsed:.2f}s = {n / elapsed:.0f} ops/sec")
    return elapsed


def read_replica_wal(offset):
    try:
        with open(REPLICA_WAL, 'rb') as f:
            f.seek(offset)
            return f.read().decode(errors='ignore')
    except FileNotFoundError:
        return ''


def measure_replication_lag(n=100, timeout_sec=5.0):
    if not os.path.exists(REPLICA_WAL):
        print(f"Replica WAL not found at {REPLICA_WAL}. Start the replica before measuring lag.")
        return None

    client = make_client()
    offset = os.path.getsize(REPLICA_WAL)
    lags = []

    for i in range(n):
        key = f"lagkey{i}"
        value = f"value{i}"
        payload = f"SET {key} {len(value)}\n{value}\n".encode()
        client.sendall(payload)
        client.recv(1024)

        target_marker = f"SET {key} {len(value)}\n"
        start = time.perf_counter()
        seen = False

        while time.perf_counter() - start < timeout_sec:
            chunk = read_replica_wal(offset)
            if target_marker in chunk:
                lag = time.perf_counter() - start
                lags.append(lag)
                offset += len(chunk)
                seen = True
                break
            time.sleep(0.005)

        if not seen:
            print(f"Warning: replica did not acknowledge {key} within {timeout_sec}s")
            lags.append(timeout_sec)
            offset = os.path.getsize(REPLICA_WAL)

    client.close()

    if not lags:
        print("No lag samples collected.")
        return None

    avg_lag = sum(lags) / len(lags)
    print(f"Replication lag: {len(lags)} samples, avg {avg_lag * 1000:.1f} ms")
    print(f"Replication lag min {min(lags) * 1000:.1f} ms, max {max(lags) * 1000:.1f} ms")
    return lags


def main():
    parser = argparse.ArgumentParser(description='Simple KV store benchmark')
    parser.add_argument('--writes', type=int, default=1000, help='Number of SET operations')
    parser.add_argument('--reads', type=int, default=1000, help='Number of GET operations')
    parser.add_argument('--lag', type=int, default=100, help='Number of replication lag samples')
    parser.add_argument('--skip-writes', action='store_true', help='Skip write benchmark')
    parser.add_argument('--skip-reads', action='store_true', help='Skip read benchmark')
    parser.add_argument('--skip-lag', action='store_true', help='Skip replication lag measurement')
    args = parser.parse_args()

    print('Starting benchmark...')
    if not args.skip_writes:
        bench_writes(args.writes)
    if not args.skip_reads:
        bench_reads(args.reads)
    if not args.skip_lag:
        measure_replication_lag(args.lag)


if __name__ == '__main__':
    main()
