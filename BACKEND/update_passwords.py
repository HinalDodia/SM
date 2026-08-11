import pymysql
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv('.env')

conn = pymysql.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', 3306)),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'investment')
)

new_hash = generate_password_hash('Change@123')
print(f"New hash: {new_hash[:40]}...")

emails = [
    'alice@gmail.com',
    'hinaldodia67678@gmail.com',
    'ashwindodia1@gmail.com',
    'rohandodia1@gmail.com',
]

cur = conn.cursor()

# Update passwords
for email in emails:
    cur.execute("UPDATE users SET password_hash = %s WHERE email = %s", (new_hash, email))
    print(f"Updated '{email}': {cur.rowcount} row(s) affected")

conn.commit()
print("\nAll passwords updated to Change@123 ✅")
conn.close()
