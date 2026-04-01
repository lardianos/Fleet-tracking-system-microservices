import json

student_json = '{"name": "Gianis", "age": 20, "courses": ["Fisiki","Mathimatika"]}'

# print(student_json)
student = json.loads(student_json)
# print(student["courses"][0])
# print(student.get("name"))

newjson = json.dumps(student)
print(student_json)
print(newjson)
