# **kwargs = parameter that will pack all arguments into a dictionary (key:value)
# useful so that a function can accept a varying amount of keyword arguments

def hello(**kwargs):
#    print("hello" +" "+ kwargs["first"] + " " +kwargs["last"])
    for key,value in kwargs.items():
        print(value)


#hello(first="pack", middle="dude",last="test")

hello({"USA":"Germany"})
