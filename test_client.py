import socket

def send_and_recv(sock, data):
    sock.send(data)
    return sock.recv(1024).decode().strip()

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('127.0.0.1', 5000))

    # SET
    resp = send_and_recv(sock, b"SET foo 3\n")
    resp2 = send_and_recv(sock, b"bar\n")
    assert resp2 == "OK", f"SET failed: expected 'OK', got '{resp2}'"

    # GET
    resp = send_and_recv(sock, b"GET foo\n")
    assert resp == "bar", f"GET mismatch: expected 'bar', got '{resp}'"

    # DELETE
    resp = send_and_recv(sock, b"DELETE foo\n")
    assert resp == "Deleted", f"DELETE failed: expected 'Deleted', got '{resp}'"

    # GET after delete — confirm it's actually gone
    resp = send_and_recv(sock, b"GET foo\n")
    assert resp != "bar", f"Expected foo to be deleted, but GET still returned 'bar'"

    sock.close()
    print("All tests passed!")

if __name__ == "__main__":
    main()
    