# index operator [] = gives acces to a sequence's ellement (str,list,tuple)
name ="stavrosPapantonakis"

if(name[0].islower()):
    name = name.capitalize()
    print(name)
first_name = name[:7].upper()
last_name = name[7:].lower()
print(first_name)
print(last_name)
last_char = name[-1]
print(last_char)
