import base64
import sqlite3
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


DB_FILE = "totally_not_my_privateKeys.db"

CREATE_KEYS_TABLE = """
CREATE TABLE IF NOT EXISTS keys(
    kid INTEGER PRIMARY KEY AUTOINCREMENT,
    key BLOB NOT NULL,
    exp INTEGER NOT NULL
)
"""

#convert int to base64 url encoding
def base64url_encode(number):
    byte_length = (number.bit_length() + 7) // 8
    number_bytes = number.to_bytes(byte_length, byteorder="big")
    return base64.urlsafe_b64encode(number_bytes).rstrip(b"=").decode("utf-8")

#generate 2048 bit rsa priv key
def generate_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)

#serialize priv key as pkcs PEM for storage
def serialize_private_key(private_key):
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


#deserialize the pem bytes back to a private key object
def deserialize_private_key(key_data):
    return serialization.load_pem_private_key(key_data, password=None)


def _row_to_key(row):
    #convert a database row into the key structure used by the app
    return {
        "kid": row[0],
        "private_key": deserialize_private_key(row[1]),
        "expires_at": row[2],
    }

#gen and insert one private key using a parameterized query
def _insert_key(connection, expires_at):
    private_key = generate_private_key()
    serialized_key = serialize_private_key(private_key)

    cursor = connection.execute(
        "INSERT INTO keys (key, exp) VALUES (?, ?)",
        (serialized_key, expires_at),
    )

    return {
        "kid": cursor.lastrowid,
        "private_key": private_key,
        "expires_at": expires_at,
    }


def initialize_database():
    #create the database and ensure expired and valid keys exist
    now = int(time.time())

    with sqlite3.connect(DB_FILE) as connection:
        connection.execute(CREATE_KEYS_TABLE)

        expired_row = connection.execute(
            "SELECT kid FROM keys WHERE exp <= ? LIMIT 1",
            (now,),
        ).fetchone()
        if expired_row is None:
            _insert_key(connection, now - 3600)

        valid_row = connection.execute(
            "SELECT kid FROM keys WHERE exp > ? LIMIT 1",
            (now,),
        ).fetchone()
        if valid_row is None:
            _insert_key(connection, now + 7200)


def get_signing_key(expired=False):     #Read an expired or valid private key from SQLite. If the requested kind of key is missing, create one before returning it.

    now = int(time.time())

    with sqlite3.connect(DB_FILE) as connection:
        connection.execute(CREATE_KEYS_TABLE)

        if expired:
            row = connection.execute(
                """
                SELECT kid, key, exp
                FROM keys
                WHERE exp <= ?
                ORDER BY exp DESC
                LIMIT 1
                """,
                (now,),
            ).fetchone()

            if row is None:
                return _insert_key(connection, now - 3600)
        else:
            row = connection.execute(
                """
                SELECT kid, key, exp
                FROM keys
                WHERE exp > ?
                ORDER BY exp ASC
                LIMIT 1
                """,
                (now,),
            ).fetchone()

            if row is None:
                return _insert_key(connection, now + 7200)

    return _row_to_key(row)


def get_valid_keys(): #read every non-expired private key from SQLite
    now = int(time.time())

    with sqlite3.connect(DB_FILE) as connection:
        connection.execute(CREATE_KEYS_TABLE)
        rows = connection.execute(
            """
            SELECT kid, key, exp
            FROM keys
            WHERE exp > ?
            ORDER BY kid
            """,
            (now,),
        ).fetchall()

    return [_row_to_key(row) for row in rows]


def key_to_jwk(key):     #convert private key record into a public JWK
    public_key = key["private_key"].public_key()
    public_numbers = public_key.public_numbers()

    return {
        "kty": "RSA",
        "kid": str(key["kid"]),
        "use": "sig",
        "alg": "RS256",
        "n": base64url_encode(public_numbers.n),
        "e": base64url_encode(public_numbers.e),
    }
