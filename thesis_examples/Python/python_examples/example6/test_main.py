try: 
		testDict = {}
		testDict["_Writing_Test_"] = "Writing_Test"
		testDict["Script_Started"] = time_stamper_for_json()

		json_printer(testDict, "file_Write_Test")

		print (f"---### File access test passed! ###---")
		#input_trigger()

except Exception as e:
	print ("hello")
	print (f"---### File access error occured ###---")
	print (f"'{e}'")
	print(f"---### Try running terminal with Administrator rights! ###---")
	print(f"---### Nothing will be saved if you decide to continue! ###---")
	print()
	while(True):
		pass
	# input_trigger()
	print("asdad")