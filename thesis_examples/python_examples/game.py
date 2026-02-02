
import random

a =[]
b =[]
c =[]
d =[]
j=0
for i in range(1, 22):
    a.append (random.randint(1,52))
print a
print "skepsou ena aritho apo to 1 eos to 21"
for i in range(1, 8):
  
    b.append (a[j])
    
    c.append (a[j+1])
   
    d.append (a[j+2])
    
    j=j+3

print b
print c
print d

for q in range(0, 3):
    se_pia = input ("se pia lista einai ")


    if se_pia == 1:
       
        a = []
        for i in range(0, 7):
            a.append (c[i])
        for i in range(0, 7):
            a.append (b[i])
        for i in range(0, 7):
            a.append (d[i])    
        
     
    if se_pia == 2:
        a = []
        for i in range(0, 7):
            a.append (b[i])
        for i in range(0, 7):
            a.append (c[i])
        for i in range(0, 7):
            a.append (d[i])    
       
    if se_pia == 3:
        a = []
        for i in range(0, 7):
            a.append (b[i])
        for i in range(0, 7):
            a.append (d[i])
        for i in range(0, 7):
            a.append (c[i])   
    print a
    j=0
    b =[]
    c =[]
    d =[]
    for s in range(1, 8):
  
        b.append (a[j])
        
        c.append (a[j+1])
       
        d.append (a[j+2])
        
        j=j+3

    print b
    print c
    print d  

print a
print a[10]




