movie_list = ["matrix", "lord of the rings", "star wars", "fight club"]
new_movie = str(input("Dose agapimeni tenia: "))
if new_movie in movie_list:
    print("exists, not saved")
else:
    movie_list.append(new_movie)
    movie_list.sort()
    print(movie_list)
    print(len(movie_list))
