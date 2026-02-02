num_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


max_num = num_list[0]
i = 0
while i < 10:
    if num_list[i] > max_num:
        max_num = num_list[i]
    i += 1

print(max_num)