text = "hello\nThis is some text\nHave a good day!"
try:
    with open("files/text2.txt", "w") as file: # Me to orisma "w" grafi ksana olo to arxio apo tin arxi
        file.write(text)                       # Me to orisma "a" litourgei san apend kai grafis sto telos tou arxeiou
except FileNotFoundError:
    print("That file was not found")
