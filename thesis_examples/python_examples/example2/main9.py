#lists
food = ["gyros","pastitsio","mousakas"]

print(food)
food[0]="pizza"
print(food)

for i in food:
    print(i)
food.append("mpoureki")
print(food)

food.sort()
print(food)

food.remove("pizza")
print(food)

food.pop()
print(food)

food.clear()
print(food)
