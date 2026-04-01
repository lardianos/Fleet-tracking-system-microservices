print("skepsou enan arithmo apo to 1 eos to 50")
max = int(100)
min = int(0)
num = int(max/2)
while True:
    #print("max:"+str(max) + " min:"+str(min)+ " num:"+str(num))
    print("Mipos einai to: " + str(num))
    answer = input("Dose apantisi Y or N: ")
    if answer == "Y" or answer == "y":
        break
    print("Eimai megalitero h miktrotero?")
    answer = input("Dose '>' h '<': ")
    if answer == ">":
        min = num
        num = min + int((max-min)/2)
    else:
        max = num
        num = max - int((max-min)/2)

print("Se katourao!!")

#50
# 25
# an > tote
# min = num = 25
# num = min + (max-num/2)= 37 (exis max=50 kai min=25)
# an > tote
# min = num = 37
# an < tote
# max = 37
# num max-min/2

# num = min + (max-num/2)= 43 (exis max=50 kai min=37)
# num min + (max-min/2) 37 + 43-37/2
# an < tote
# max = 25
# num = max - max+num/2
# 25 /2 = 12

# 37
# an > tote min + (max-num/2) =
#37
# 25 + 37-25 /2
#
#
#
