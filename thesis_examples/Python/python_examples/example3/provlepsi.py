import random

def spread(cards):
    listA = []
    listB = []
    listC = []
    for i in range(0,20,3):
        listA.append(cards[i])
        listB.append(cards[i+1])
        listC.append(cards[i+2])
    cards.clear()

    print("\nOmada A: "+str(listA) +"\nOmada B: "+ str(listB)+ "\nOmada C: " + str(listC))
    choice = input("Se pia omada vriskete o arithmos sou? : ")
    if(choice == "A" or choice == "a"):
        cards.extend(listB)
        cards.extend(listA)
        cards.extend(listC)
    elif(choice == "B" or choice == "b"):
        cards.extend(listA)
        cards.extend(listB)
        cards.extend(listC)
    elif(choice == "C" or choice == "c"):
        cards.extend(listB)
        cards.extend(listC)
        cards.extend(listA)
    return cards

cards= [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21]
random.shuffle(cards)
while True:
    print("Dialekse enan apo tous aritmous kai thimisou ton"+"\n"+str(cards)+"\n")
    hotkey = input("Dose (Y) gia na sinexisi H (E) gia Exit: ")
    if(hotkey == "e" or hotkey=="E"):
        break
    elif(hotkey == "Y" or hotkey == "y"):
        for i in range(0,3):
            cards = spread(cards)
        print("\no arithmos pou skeftikes einai to : [", cards[10],"] \n")
