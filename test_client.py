import socket

def send_line(sock, data):
    sock.send(data)

def recv_response(sock):
    return sock.recv(1024).decode().strip()

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('127.0.0.1', 5000))
    sock.settimeout(5)

    # SET
    send_line(sock, b"SET foo 3\n")
    send_line(sock, b"bar\n")
    resp = recv_response(sock)
    assert resp == "OK", f"SET failed: expected 'OK', got '{resp}'"

    # GET
    send_line(sock, b"GET foo\n")
    resp = recv_response(sock)
    assert resp == "bar", f"GET mismatch: expected 'bar', got '{resp}'"


    # DELETE
    send_line(sock, b"DELETE foo\n")
    resp = recv_response(sock)
    assert resp == "Deleted", f"DELETE failed: expected 'Deleted', got '{resp}'"

    # GET after delete — confirm it's actually gone
    send_line(sock, b"GET foo\n")
    resp = recv_response(sock)
    assert resp != "bar", f"Expected foo to be deleted, but got: '{resp}'"

    sock.close()
    print("All tests passed!")

if __name__ == "__main__":
    main()
    