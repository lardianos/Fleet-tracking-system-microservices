#Na grafi programa pou tha dexete apo to pliktrologio to plithos oron, lepton, defterolepton
# kai tha tiponi stin othoni tin ora stin morfi: OO:LL:DD

# kalo einai na apothikevoume ta dedomena stin sosti morfi
h = int(input("Dose ores: "))
m = int(input("Dose lepta: "))
s = int(input("Dose defterolepta: "))

if(h < 10):
    s_h = "0"+str(h)
else:
    s_h = str(h)
if(m < 10):
    s_m = "0"+str(m)
else:
    s_m = str(m)
if(s < 10):
    s_s = "0"+str(s)
else:
    s_s = str(s)

time = s_h + ":" + s_m + ":" + s_s
print(time)