friend_list = ["Luffy", "Songoku", "Naruto"]
party_list = ["Luffy", "Adam", "Bob", "Jenny", "Mira", "Nick", "Johne", "Drake", "Mery", "Naruto"]

# party_cntr = 0
# for  guest in party_list:
#     for friend in friend_list:
#         if guest == friend:
#             party_cntr += 1
# if party_cntr < 2:
#     print("Den erxome")
# else:
#     print("Erxome trexontas")

party_cntr = 0
for friend in friend_list:
    if friend in party_list:
        party_cntr += 1
if party_cntr < 2:
    print("Den erxome")
else:
    print("Erxome trexontas")

