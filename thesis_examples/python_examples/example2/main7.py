#create a substring from a string. string slicing
#index[]
#slice()
#[start:stop:step]

name = "Stavros Papantonakis"
first_name = name[0:7]# = :7 to start periexete, to stop den periexete
last_name = name[8:]# = 8:telos
crazy_name = name[::2]# apo tin arxi mexri telous me vima dio
reverced_name = name[::-1]#

url1 = "http://google.com"
slice = slice(7,-4)# epistrefi ena antikimeno isaksio tou bracket
print(name)
print(first_name)
print(last_name)
print(crazy_name)
print(reverced_name)
print(url1[7:-4])
print(url1[slice])
x=5
if not( x > 10):
    print("aaa")
print(f"hello {name}")
print(f"{x=}")
print(f"{255:b}")          
