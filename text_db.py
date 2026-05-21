import oracledb

conn = oracledb.connect(
    user="DBS_LAB",
    password="dbslab123",
    dsn="127.0.0.1:1521/freepdb1"
)

print("CONNECTED SUCCESSFULLY")
