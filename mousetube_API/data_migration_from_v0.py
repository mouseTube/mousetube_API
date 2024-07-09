'''
Created by Nicolas Torquet at 09/07/2024
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
'''


from tkinter import filedialog as fd
import pandas as pd
import json
import re


# def splitStringForComaOutsideQuotes(text: str):
#     for char in text:
#         if char == "'":


if __name__ == '__main__':
    dataFile = fd.askopenfile(filetypes=[("txt files", "*.txt")], title="Choose a data file")
    f = open(dataFile.name, 'r', encoding="utf8")
    userRaw = f.read()

    COMMA_MATCHER = re.compile(r",(?=(?:[^\"']*[\"'][^\"']*[\"'])*[^\"']*$)")

    userList = userRaw.split('),(')
    userList[0] = userList[0].split('(')[1]
    for i in range(0, len(userList)):
        # userList[i] = userList[i].split(',\'')
        # userList[i] = re.split(r',(?=")', userList[i])
        userList[i] = COMMA_MATCHER.split( userList[i])
        for j in range(0, len(userList[i])):
            userList[i][j] = userList[i][j].replace('\"', '')
            userList[i][j] = userList[i][j].replace('\'', '')

    for i in range(len(userList)):
        if len(userList[i]) > 14:
            print(userList[i])

    table = pd.DataFrame(userList, columns=["id_user", "name_user", "first_name_user", "email_user", "phone_user",
	    "unit_user", "institution_user", "address_user", "country_user", "login_user", "password_user", "administrator",
	    "salt", "confirmcode"])


    for i in range(0, len(table)):
        table.iloc[i]