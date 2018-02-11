import psycopg2.extras
import time

start = time.time()
db_pass = open('../../instance/password.txt').read().splitlines()[0]


def connect(database_name):
    try:
        connection_ = psycopg2.connect(
            database=database_name, user='openatlas', password=db_pass, port=5432, host='localhost')
        connection_.autocommit = True
        return connection_
    except Exception as e:  # pragma: no cover
        print(database_name + " connection error.")
        raise Exception(e)


dpp_origin_connect = connect('openatlas_dpp_origin')
dpp_connect = connect('openatlas_dpp')
ostalpen_connect = connect('ostalpen')

print('Execution time: ' + str(int(time.time() - start)) + ' seconds')
