# write some data to a file, and track the byte position of each line
with open("data.txt", "w") as f:
    pos1 = f.tell()      # tell() = "what byte am I at right now?"
    f.write("apple\n")

    pos2 = f.tell()
    f.write("banana\n")

    pos3 = f.tell()
    f.write("cherry\n")

print(f"apple starts at byte {pos1}")
print(f"banana starts at byte {pos2}")
print(f"cherry starts at byte {pos3}")

with open("data.txt", "r") as f:
    f.seek(15)  # jump straight to byte 13
    line = f.readline()
    print(line)