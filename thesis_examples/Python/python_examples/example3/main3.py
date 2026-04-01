# *args = parameter that will pack all arguments into a tuple (ordered, unchangeable)
#   useful so that a function can accept a varying amount of arguments

def add(*args):
    result = 0
    for number in args:
        result+=number
    return result


print(add(1,2,3))
