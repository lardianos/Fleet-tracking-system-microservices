rand_num = 15
end_game = 5

for i in range(0,end_game):
    print("exis", (end_game - i), " prospathies")
    a = int(input("Give a number: "))
    if a == rand_num:
        print("To Vrikes se",end_game-i,"prospathies!!")
        break
    else:
        if a > rand_num:
            print("Dose mikrotero")
        else:
            print("dose megalitero")
else:
    print("Exases!!!")