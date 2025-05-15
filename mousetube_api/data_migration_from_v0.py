"""
Created by Nicolas Torquet at 09/07/2024
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
"""

from tkinter import filedialog as fd
import pycountry


# def splitStringForComaOutsideQuotes(text: str):
#     for char in text:
#         if char == "'":


def getCountryCodeFromCountryName(countryName):
    for country in pycountry.countries:
        if country.name.lower() == countryName.lower():
            return country.alpha_2
    return ""


if __name__ == "__main__":
    dataFile = fd.askopenfile(
        filetypes=[("txt files", "*.txt")], title="Choose a data file"
    )
    f = open(dataFile.name, "r", encoding="utf8")

    #################### USER TABLE ####################
    """
    userRaw = f.read()
    
    
    countries = []

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


    conn = pymysql.connect(
    host='localhost',
    port=3307,
    user='mousetube_webapp',
    password='giVe@cce552d@t@Base',
    db='mousetube',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for i in range(0, len(table)):
        if table.iloc[i]['country_user']:
            codeCountry = getCountryCodeFromCountryName(table.iloc[i]['country_user'])
        else:
            codeCountry = ""

        if table.iloc[i]['confirmcode'] == 'y':
            id = int(table.iloc[i]['id_user'])
            sql = f"SELECT * FROM auth_user WHERE id = {id}"
            cursor.execute(sql)

            rows = cursor.fetchall()
            # print(len(rows))
            if len(rows) > 0:
                for row in rows:
                    print(row)
                # check if userprofile exists
                sql_check_userprofile = f"SELECT * FROM mousetube_api_userprofile WHERE id = {id}"
                cursor.execute(sql_check_userprofile)
                profile = cursor.fetchall()
                if len(profile) > 0:
                    sql_update_userprofile = f"UPDATE mousetube_api_userprofile SET phone = '{table.iloc[i]['phone_user']}', unit = '{table.iloc[i]['unit_user']}', institution = '{table.iloc[i]['institution_user']}', address = '{table.iloc[i]['address_user']}', country = '{codeCountry}' WHERE id = {id}"
                else:
                    sql_update_userprofile = f"INSERT INTO mousetube_api_userprofile (id, phone, unit, institution, address, country, created_by_id, user_id, modified_at) VALUES ({id}, '{table.iloc[i]['phone_user']}', '{table.iloc[i]['unit_user']}', '{table.iloc[i]['institution_user']}', '{table.iloc[i]['address_user']}', '{codeCountry}', 3, {id}, '{now}')"
                cursor.execute(sql_update_userprofile)
                conn.commit()

            else:
                print(f"INSERT INTO auth_user (id, username, first_name, last_name, password, email, date_joined) VALUES ({id}, '{table.iloc[i]['login_user']}', '{table.iloc[i]['first_name_user']}', '{table.iloc[i]['name_user']}', '{table.iloc[i]['password_user']}', '{table.iloc[i]['email_user']}', '{now}')")

                print("-----------")

                print(f"INSERT INTO mousetube_api_userprofile (id, phone, unit, institution, address, country, created_by_id, user_id) VALUES ({id}, '{table.iloc[i]['phone_user']}', '{table.iloc[i]['unit_user']}', '{table.iloc[i]['institution_user']}', '{table.iloc[i]['address_user']}', '{codeCountry}', 3, {id})")

                # sql_insert_user = "INSERT INTO auth_user (id, username, first_name, last_name, password, email) VALUES (%i, '%s', '%s', '%s', '%s', '%s')"
                # cursor.execute(sql_insert_user, (id, table.iloc[i]['login_user'],table.iloc[i]['first_name_user'], table.iloc[i]['name_user'],
                #                             table.iloc[i]['password_user'], table.iloc[i]['email_user']))

                sql_insert_user = f"INSERT INTO auth_user (id, username, first_name, last_name, password, email, date_joined) VALUES ({id}, '{table.iloc[i]['login_user']}', '{table.iloc[i]['first_name_user']}', '{table.iloc[i]['name_user']}', '{table.iloc[i]['password_user']}', '{table.iloc[i]['email_user']}', '{now}')"
                cursor.execute(sql_insert_user)
                conn.commit()

                # sql_insert_userprofile = ("INSERT INTO mousetube_api_userprofile (id, phone, unit, institution, address, country, created_by_id, user_id) VALUES ("
                #                           "%i, '%s', '%s', '%s', '%s', '%s', %i, %i)")
                # cursor.execute(sql_insert_userprofile, (id, table.iloc[i]['phone_user'], table.iloc[i]['unit_user'], table.iloc[i]['institution_user'],
                #                             table.iloc[i]['address_user'], table.iloc[i]['country_user'], 3, id))
                sql_insert_userprofile = f"INSERT INTO mousetube_api_userprofile (id, phone, unit, institution, address, country, created_by_id, user_id, modified_at) VALUES ({id}, '{table.iloc[i]['phone_user']}', '{table.iloc[i]['unit_user']}', '{table.iloc[i]['institution_user']}', '{table.iloc[i]['address_user']}', '{codeCountry}', 3, {id}, '{now}')"
                cursor.execute(sql_insert_userprofile)
                conn.commit()

    conn.close()
    """

    #################### PROTOCOL TABLE ####################
