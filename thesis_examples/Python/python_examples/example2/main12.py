#set - collection which is unordered, unindexed no  duplicate values

kouzinika={"fork","spoon","knife"}
dishes={"bowl","plate","cup"}

kouzinika.add("piato")

for x in kouzinika:
    print(x)
print("-------add--------")

kouzinika.remove("fork")
for x in kouzinika:
    print(x)
#kouzinika.clear()
print("-------remove--------")

for x in kouzinika:
    print(x)


print("-------clear-------")

kouzinika.update(dishes)#
for x in kouzinika:
    print(x)
print("-------update-------")
dinner_table = kouzinika.union(dishes)
for x in dinner_table:
    print (x)
print("-------dinner_table-------")

print(dishes.difference(kouzinika))
print(dishes.intersection(kouzinika))
print("-------diff kai intersection-------")
