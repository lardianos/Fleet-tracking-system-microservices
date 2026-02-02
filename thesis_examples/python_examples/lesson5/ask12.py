N = 5
next_odd = 1
for j in range(0, N):
    for i in range(0,N - j):
        print(" ",end=" ")
    for l in range(0, next_odd):
        print("*", end=" ")
    else:
        next_odd += 2
    print("")