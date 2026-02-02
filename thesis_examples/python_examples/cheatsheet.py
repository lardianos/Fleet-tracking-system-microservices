help("modules")

################## Metavlites ###################
#################################################

first_name = "joHn"
last_name = "Smith"
name = "proto test"

Nikos = giorgos= 30
maria = 35
giannis = 25

print(name)
print(type(name))
print(first_name + " " + last_name)
print(str(Nikos)+ " " + str(maria) + " " + str(giannis)+ " " +str(giorgos))


#################### Strings ####################
#################################################

print(len(first_name)) # Epistrefi to mikos
print(first_name.find("o")) # Epistrefi to index(tin thesi tou protou xaraktira) tou protou alpharithmitikou pou tha vri mesa sto string
print(first_name.capitalize()) # Epistrefi string me to Proto kefaleo kai ta ipolipa mikra
print(first_name.upper()) # Epistrefi string ola KEFALEA
print(first_name.lower()) # Epistrefi string me ola mikra
print(first_name.isdigit()) # Epistrefi True an einai psifio alios Epistrefi False
print(age.isdigit())
print(first_name.isalpha()) # Epistrefi True an einai xaraktiras alios Epistrefi False
print(first_name.count("o")) # Epistrefi ton arithmo ton alpharithmitikon pou vrike sto string
print(first_name.replace("o","a")) # Epistrefi ena string opou exei antikatisti to prota alpha me ta deftero alpha
print(first_name*3) #emfanizei 3 fores to string

    #############################################################
    ####   Create a substring from a string. string slicing   ###
    #      index[]
    #      slice()
    #      [start:stop:step]
    #############################################################

name = "Stavros Papantonakis"
first_name = name[0:7]# = :7 to start periexete, to stop den periexete
last_name = name[8:]# = 8:telos
crazy_name = name[::2]# apo tin arxi mexri telous me vima dio
reverced_name = name[::-1]# apo tin arxi os to telos me vima -1

url1 = "http://google.com"
slice = slice(7,-4)# Epistrefi ena antikimeno isaksio tou bracket
print(url1[7:-4])

print(f"hello {name}")
print(f"{x=}")
print(f"{255:b}")

expr= input("Dose praksi: ") # 1+2+3
eval(expr) # ekteli entoles tis python epomenos epistrefi to apotelesma 
#################### Type casting ###############
#################################################

a= 2 #int
b= 1.0#float
c= "3"#string
d= "4"#string

print(a)
print(b)
print(c+d)

a=float(a)
b=int(b)
c=int(c)
d=float(d)

##################### Input #####################
#################################################

name = input("whats your name: ")

##################### Math #####################
#################################################

import math

pi= 3.14
x = 3
y = 2
z = 1

print(round(pi)) # kanei strogilopihsi
print(math.ceil(pi))# Epistrefi ton kontinotero akereo pros ta pano
print(math.floor(pi)) # Epistrefi ton kontinotero akereo pros ta kato
print(abs(pi)) # Epistrefi tin apoliti timi
print(pow(pi,2)) # Epistrefi tin dinami
print(math.sqrt(pi)) # Epistrefi tin tetragoniki riza
print(max(x,y,z)) # Epistrefi to max
print(min(x,y,z)) # Epistrefi to min

##################### Break Continue Pass #####################
###############################################################

break
continue
pass

##################### Time ####################################
###############################################################

import time
time.sleep(1) #sleep for 1 second

##################### Lists ###################################
###############################################################

food = ["gyros","pastitsio","mousakas"]
food[0]="pizza" # Mporoume na grapsoume se kathe thesi tis listas me to index
print(food)

for i in food: # Mporoume na treksoume tin lista se mia for
    print(i)

food.append("mpoureki") # prostheti kati sto telos tis listas
food.sort() # kani taksinomisi tin lista
food.remove("pizza") # aferi kati apo mia lista
food.pop() # mas Epistrefi to telefteo stixio tis listas kai to aferi
food.clear() # adiazei tin lista

        ###########################################################
        ############# 2D+ lists  dio plus diastaseon ##############
        ###########################################################

dishes=["gyros","astitsio","pizza"]
drinks=["cola","beer","whiskey"]
desserts=["pagoto","pancakes"]

food = [drinks,dishes,desserts]
print(food[0][1][0])


######################### Tuples ################################
#################################################################
###    tuple = collection which is ordered and unchangeable   ###
###    used to group toogether related data                   ###
###    den mporoume na prostesoume h na aferesoume dedomena   ###
#################################################################

student = ("stavros",22,"male")
print(student[0])
for x in student:
    print(x)
student.count("Stavros") # Epistrefi ton arithmo ton alpha
student.index("male") # Epistrefi tin thesi tou

########################### Set #################################
#################################################################
###             collection which is unordered,                ###
###             unindexed no duplicate values (agnoounte)     ###
#################################################################

kouzinika={"fork","spoon","knife"}
dishes={"bowl","plate","cup"}
for x in kouzinika:
    print(x)
kouzinika.add("piato") # prostheti kati se ena set
kouzinika.remove("fork") # aferi kati apo to set
kouzinika.clear() # adiazei to set
kouzinika.update(dishes) # prostheti sto set ta dedomena apo ena alo set
dinner_table = kouzinika.union(dishes) # Epistrefi tin enosi dio set
dishes.difference(kouzinika) # epistrefi tis diafores anamesa se dio set
dishes.intersection(kouzinika) # epistrefi ta koina anamesa se dio set

########################### Dictionary ##########################
#################################################################
###             dictionary = a changable, unordered           ###
###             collection of unique key:value pairs,         ###
###             fast becouse they ise hashing,                ###
###             allow us to acces a value quickly             ###
#################################################################

capitals = {
    "USA":"Washington",
    "Germany":"Berlin",
    "Rissoa":"Moscow"}

for key,values in capitals.items():
    print(key,values)

capitals.get("Greece") # sou epistrefi to value gia to key pou edoses
capitals.keys() # sou epistrefi ta keys tou dictionary
capitals.values() # sou epistrefi ta values tou dictionary
capitals.items() # sou epistrefi to periexomeno tou dictionary se zevgaria
capitals.update({"Greece":"Athens"}) # prosthetis ena zevgari key:value sto dictionary
capitals.pop("USA") # aferi to zevgari me to klidi pou tou edoses
capitals.clear() # adiazei to dictionary

##################### Index operator [] #######################
###############################################################
###         gives acces to a sequence's ellement            ###
###         (str,list,tuple)                                ###
###############################################################

name ="stavrosPapantonakis"
if(name[0].islower()):# an o xaraktiras einai mikros epistrefi True
    name = name.capitalize()
first_name = name[:7].upper() # apo to 0 eos kai to 6 ginonte kefalea
last_name = name[7:].lower() # apo to 7 eos telous ginonte lower
last_char = name[-1] # o telefteos xaraktiras



########################  Functions  ##########################
###############################################################
####            Positional arguments                        ###
###############################################################

def hello(name):
    return name
print(hello("stavros"))

        ################## Keyword arguments #######################
        ############################################################

def hello(first,second,third):
    print(first,second,third)
hello(second="1",first=2,third=3)

        ########################  *args  ##############################
        ###############################################################
        ###         parameter that will pack all arguments          ###
        ###         into a tuple (ordered, unchangeable)            ###
        ###         useful so that a function can accept            ###
        ###         a varying amount of arguments                   ###
        ###############################################################
        # mas epitrepi na exoume osa orismata mas dothoun kathe fora
        # den mporoume omos na epireasoume ta dedomena pou dexomaste
        # an thelome mporoume na ta alaksoume mporoume na to metatrepsoume
        # se lista me typecasting
        # args = list(args)

def add(*args):
    result = 0
    for number in args:
        result+=number
    return result

print(add(1,2,3))

        ########################  **kwargs  ###########################
        ###############################################################
        ###         parameter that will pack all arguments          ###
        ###         into a dictionary (key:value)                   ###
        ###         useful so that a function can accept            ###
        ###         a varying amount of keyword arguments           ###
        ###############################################################

def hello(**kwargs):
    for key,value in kwargs.items():
        print(value)

hello({"USA":"Germany"})


def hello(**kwargs):
    print("hello" +" "+ kwargs["first"] + " " +kwargs["last"])

hello(first="pack", middle="dude",last="test")


#########################  Random  ############################
###############################################################
import random

random.randint(1,6) # epistrefi enan tixeo arithmo apo to 1 - 6
random.random() # epistrefi enan arithmo 0 eos to 1

myList =["Petra","Psalidi","Xarti"]
random.choice(myList) # epistrefi ena tixeo stixio mesa apo tib lista

cards = [1,2,3,4,5,6,7,8,9,"J","Q","K","A"]
random.shuffle(cards) # anakatevi ta stixia tis listas pou tou dinis


#######################  Exceptions  ##########################
###############################################################

try:

    numerator = int(input("Enter a number: "))
    denominator = int(input("Enter a number: "))

    result = numerator/denominator
except ZeroDivisionError as e: # kanoume handle to exception
    print(e)
    print("den mporeis na kaneis dieresi me to 0")
except ValueError as e:
    print(e)
    print("den edoses arithmo")
except Exception as e:
    print(e)
    print("something went wrong")
else:
    print(result) # an ola pigan kala ektelite aftos o kodikas
finally:
    print("This will always execute") # kai aftos o kodikas ektelite panta


##########################  Files  ############################
###############################################################

import os

path_wsl = "//mnt//c//Users//BeastBox//Desktop//thesis_examples//python_examples//example4/files//test.txt"
path_win = "C:\\Users\\BeastBox\\Desktop\\thesis_examples\\python_examples\\example4\\files\\test.txt"

if os.path.exists(path_wsl):
    print("that location exists!")
    if os.path.isfile(path_wsl):
        print("this is file")
    elif os.path.isdir(path_wsl):
        print("this is directory")
else:
    print("that location does not exist!")

        ########################  Copy Files  #########################
        ###############################################################
        ###         copyfile() = copies contents of a file          ###
        ### ------------------------------------------------------- ###
        ###         copy() = copufile() + permission mode           ###
        ###                     + destination can be a directory    ###
        ### ------------------------------------------------------- ###
        ###         copy2() = copy() + copies metadata              ###
        ###         (files creation and modification times)         ###
        ###############################################################

import shutil
try:
    shutil.copyfile("files/text.txt","copy.txt")#src,dst
    #antigrafi arxio se arxio
except:
    print("File not found")


        ########################  Read File   #########################
        ###############################################################

try:
    with open("files/text.txt") as file:
        print(file.read())
    print(file.closed) # mas epistrefi True an to arxio exei klisi kai False an to arxio einai anixto
except FileNotFoundError:
    print("That file was not found")

        ########################  Write File   ########################
        ###############################################################

text = "hello\nThis is some text\nHave a good day!"
try:
    with open("files/text2.txt", "w") as file: # Me to orisma "w" grafi ksana olo to arxio apo tin arxi
        file.write(text)                       # Me to orisma "a" litourgei san apend kai grafis sto telos tou arxeiou
except FileNotFoundError:
    print("That file was not found")

        ########################  Move File   #########################
        ###############################################################

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

        ########################  Delete File   #######################
        ###############################################################

path = "files/destination.txt"

try:
    os.remove(path) # diagrafi ena arxio
    os.rmdir(path) # diagrafi ena adio directory
    shutil.rmtree(path) # diagrafi ton fakelo kai to periexomeno tou

except FileNotFoundError:
    print("to arxio den iparxei")
except PermissionError:
    print("den exeis dikeoma na to svisis")
else:
    print("svistike!")

######################   Modules   ############################
###############################################################
###         a file containing code that you want            ###
###         to include in your program                      ###
###         use "import" to include a module                ###
###         useful to break up a large program into         ###
###         reusable separate files                         ###
###############################################################

import math
import math as m
from math import pi

print(math.pi)
print(m.pi)
print(pi)

#------- file my_module.py -----

my_variable = "kolokithi"

def print_hello():
    return "hello world!"


#-------file main.py -----------
import my_module as md

print(md.my_variable)

k = md.print_hello()
print(k)
