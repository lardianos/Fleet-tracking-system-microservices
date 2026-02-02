# copyfile() = copies contents of a file
#copy() = copufile() + permission mode + destination can be a directory
#copy2() = copy() + copies metadata (files creation and modification times)

import shutil

try:

    shutil.copyfile("files/text.txt","copy.txt")#src,dst
    #antigrafi arxio se arxio
except:
    print("File not found")
