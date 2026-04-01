num_list = []

num = int(input("Dose Enan Arithmo Apo 3 - 20: "))

while num < 3 or num > 20:
    print("Edoses lathos arithmo, parakalo ksanaprospathise")
    num = int(input("Dose Enan Arithmo Apo 3 - 20: "))

for i in range(0, num):
    a = int(input("Dose akereo "+str(i+1)+": "))
    num_list.append(a)

num_list.sort()
print(num_list)