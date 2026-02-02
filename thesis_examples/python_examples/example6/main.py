import math
# name = input("Dose onoma: ")
# surname = input("dose epitheto: ")

# full_name = name + " " + surname
# print(full_name)
#   o e o e o e o e o e  o  e  o  e  o  e  o
# 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17
# A p p l i e d M a t h  e  m  a  t  i  c  s
# akolouthia = "AppliedMathematics"

# print(akolouthia[:6]) # first 6 chars
# len = akolouthia.__len__()
# print(akolouthia[len-5:])# last 5 chars
# print(akolouthia[-5::]) # last 5 chars
# print(akolouthia[2::2]) # start from 3rd char and skip 1 char
# print(akolouthia[::-1]) # start from the last char

# even = akolouthia[2::2] # even chars
# odd = akolouthia[1::2] # odd chars

# print(even+ " " +odd)


# name = input("dose onoma: ")
# age = int(input("dose ilikia: "))

# days = age*365 
# print(name+", you are "+str(days)+" days old.")

# x = float(input("Dose X: "))
# y = float(input("Dose Y: "))

# r = math.sqrt(pow(x,2)+pow(y,2))
# print("exei apostasi "+ str(r))


# name = input("Dose onoma: ")

# print(name[1:-1:])

# s = input("dose simvolosira: ")

# s_new = s+s[::-1]
# print(s_new)

# m = int(input("dose arimo m: "))
# n = int(input("dose arimo n: "))

# print(str(m)*m + str(n)*n)

#name = input("dose onoma: ")

#print(name.replace("os","akis"))
#print(name[:-2:]+"akis")
#new_name = name[slice(None,-2,None)]
#print(new_name+"akis")

# expr= input("Dose praksi: ")
# print (eval(expr))
# 
# print(int(praksis))


# fonien = ["a","e","i","o","u"]

# data = input("dose grama: ")

# if(data in fonien):
#     print("einai fonien!")
# else:
#     print("einai simfono!")


a = input("dose a: ") #3
b = input("dose b: ") #2
c = input("dose c: ") #1

   
if(a>b and a>c): 
    print(a,end="")
elif(b>a and b>c):
    print(b,end="")
else:
    print(c,end="")

#  3<2  &  3<1
if((a<b and a>c) or (a<c and a>b)): 
    print(a,end="")
#  2>1 and 2<3
elif((b<a and b>c) or (b<c and b>a)):
    print(b,end="")
else: 
    print(c,end="")


if(a<b and a<c):
    print(a,end="")
elif(b<a and b<c):
    print(b,end="")
else:
    print(c,end="")

print("")

    