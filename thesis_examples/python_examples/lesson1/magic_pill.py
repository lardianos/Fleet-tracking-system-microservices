name = input("Type youre name: ")
surname = input("Type youre surname: ")
age = int(input("Type your age: "))
magic_pill = 10
age -= magic_pill
message_name = "Hello " + name + " " + surname
message_age = ". You are " +str(age) + " years old!"
message = message_name + message_age
print(message)