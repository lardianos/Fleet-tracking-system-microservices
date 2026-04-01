import os

path_wsl = "//mnt//c//Users//BeastBox//Desktop//thesis_examples//python_examples//example4/files//test.txt"
path_win = "C:\\Users\\BeastBox\\Desktop\\thesis_examples\\python_examples\\example4\\files\\test.txt"

if os.path.exists(path_wsl) or os.path.exists(path_win):
    print("that location exists!")
    if os.path.isfile(path_wsl) or os.path.isfile(path_win):
        print("this is file")
    elif os.path.isdir(path_wsl) or os.path.isdir(path_win):
        print("this is directory")
else:
    print("that location does not exist!")
