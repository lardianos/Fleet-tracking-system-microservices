import json

from urllib.request import urlopen

with urlopen('https://api.chucknorris.io/jokes/random') as response:
    data = json.loads(response.read())
print(data["value"])    