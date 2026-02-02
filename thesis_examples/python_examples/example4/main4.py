import os

source = "source.txt"

destination = "files//destination.txt"

try:
    if os.path.exists(destination):
        print("Threre is already a file there")
    else:
        os.replace(source,destination)
        print("metaferthike!")
except FileNotFoundError:
    print("that file was not found")
except FileExistsError:
    print("afto to arxio iparxei")
