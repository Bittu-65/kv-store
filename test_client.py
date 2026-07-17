import socket

def send_command(sock, line):
    sock.send((line + "\n").encode())
    print(">>>", line)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 5000))

# SET foo bar
value = "bar"
send_command(sock, f"SET foo {len(value)}")
sock.send((value + "\n").encode())
print("<<<", sock.recv(1024).decode())

# GET foo
send_command(sock, "GET foo")
print("<<<", sock.recv(1024).decode())

# DELETE foo
send_command(sock, "DELETE foo")
print("<<<", sock.recv(1024).decode())

sock.close()