#dictionary = a changable, unordered collection of unique key:value pairs
# fast becouse they ise hashing, allow us to acces a value quickly

capitals = {
    "USA":"Washington",
    "Germany":"Berlin",
    "Rissoa":"Moscow"}

print(capitals.get("Washington"))
print(capitals.keys())
print(capitals.values())
print(capitals.items())
for key,values in capitals.items():
    print(key,values)

print(capitals)
capitals.update({"Greece":"Athens"})
print(capitals.items())
capitals.pop("USA")
print(capitals.items())
capitals.clear()
