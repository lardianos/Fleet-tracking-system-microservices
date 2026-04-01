value_a = int(input("Dose akereo: "))
value_b = int(input("Dose akereo: "))
value_c = int(input("Dose akereo: "))

max_val = value_a

if(value_b > max_val):
    max_val = value_b
if(value_c > max_val):
    max_val = value_c
print(max_val)