def HelloWorldXY(x, y):
    if(x<10):
        print("hello world, x was < 10")
    elif(x<20):
        print("hello world, x was < 10")
    else:
        print("hello world, x wa >= 20")
    return x + y

for i in range(8, 25, 5):    
    print("--- Now running with i: {}".format(i))
    r=HelloWorldXY(i,i)
    print("result from helloWorld:{} {}".format(i,r))

# print("hello world!")
print("hello world")
# print(HelloWorldXY(1,2))

print("----------------------")

print("Interate over the items. `range(2)` is like a list [0,1].")
for i in range(2):
    print(i)

print("Iterate over an actual list.")
for i in [0,1]:
    print(i)

print("while")
i = 0
while i < 2:
    print(i)
    i+=1

print("Pyhton supports standard key words like continue and break")
while True:
    print("Entered while")
    break
    