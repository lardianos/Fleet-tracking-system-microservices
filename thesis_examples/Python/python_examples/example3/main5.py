# random
import random
num_count = {1:0,2:0,3:0,4:0,5:0,6:0}
for i in range(0,100):
     x = random.randint(1,6)
     #print(num_count[x])
     num_count[x] += 1
     #a.update({x:int(a.get(x))+1})

     #print(a.get(x))
     #if x == a.get(x):
    #     print("test")
     #print(x)
#print(num_count)



myList =["Petra","Psalidi","Xarti"]

z = random.choice(myList)
print(z)

cards = [1,2,3,4,5,6,7,8,9,"J","Q","K","A"]
random.shuffle(cards)
print(cards)
