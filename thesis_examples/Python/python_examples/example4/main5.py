import os
#
path = "files/destination.txt"

try:
    os.remove(path)
except FileNotFoundError:
    print("to arxio den iparxei")
except PermissionError:
    print("den exeis dikeoma na to svisis")
else:
    print("svistike!")
