import pymysql
from pymysql.cursors import DictCursor


def get_db():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="root123",
        database="recommendation_db",
        cursorclass=DictCursor  
    )
