value_a = int(input("Dose akereo: "))
value_b = int(input("Dose akereo: "))
value_c = int(input("Dose akereo: "))

# max_val = value_a
#
# if(value_b > max_val):
#     max_val = value_b
# if(value_c > max_val):
#     max_val = value_c
# print(max_val)

if((value_a >= value_b) and (value_a >= value_c)):
    print(value_a)
elif((value_b >= value_a) and (value_b >= value_c)):
    print(value_b)
else:
    print(value_c)