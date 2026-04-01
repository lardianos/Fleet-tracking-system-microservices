# Exceptions = events detected during execution that interrupt the flow of a program

try:

    numerator = int(input("Enter a number: "))
    denominator = int(input("Enter a number: "))

    result = numerator/denominator
except ZeroDivisionError as e:
    print(e)
    print("den mporeis na kaneis dieresi me to 0")
except ValueError as e:
    print(e)
    print("den edoses arithmo")
except Exception as e:
    print(e)
    print("something went wrong")
else:
    print(result)
finally:
    print("This will always execute")
