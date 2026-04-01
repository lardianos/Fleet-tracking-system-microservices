import numpy as np #Make numpy available using np

#create a numpy array, and append an element

a = np.array(["Hello","World"])
a = np.append(a,"!")
print("Current array: {}".format(a))
print("Printing each element")
for i in a:
    print(i)

print(a[0])
print(a[1])
print(a[2])

for i in range(3):
    print(a[i])

print("\nPrinting each element and their index")
for i,e in enumerate(a):
    print("Index: {}, was: {}".format(i,e))