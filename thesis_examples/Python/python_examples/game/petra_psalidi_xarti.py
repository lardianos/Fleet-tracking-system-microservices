import random

moves = ("rock","scissors","paper")
nums = ("1","2","3")
run = True
while run:
    computer_choice = random.choice(moves)
    player_choice = None
    print("Dialekse Kinisi.")

    while((player_choice not in nums)):
        player_choice = str(input("(1)-gia rock (2)-gia scissors (3)-gia paper: "))

    if(moves[int(player_choice)-1] == computer_choice):
        print("("+computer_choice+") isopalia!\n")
    elif(moves[int(player_choice)-1] == "paper" and computer_choice == "rock"):
        print("("+computer_choice+") kerdises!\n")
    elif(moves[int(player_choice)-1] == "scissors" and computer_choice == "paper"):
        print("("+computer_choice+") kerdises!\n")
    elif(moves[int(player_choice)-1] == "rock" and computer_choice == "scissors"):
        print("("+computer_choice+") kerdises!\n")
    else:
        print("("+computer_choice+") Se katourisa!!\n")

    if(input("thes na sinexisis (y,n)").lower() == ("n")):
        run = False
