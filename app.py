import time

import jwt
from flask import Flask, jsonify, request

from keys import get_signing_key, get_valid_keys, initialize_database, key_to_jwk


app = Flask(__name__)

# create and open totally_not_my_privateKeys.db when the application starts
initialize_database()


@app.route("/.well-known/jwks.json", methods=["GET"])
def jwks(): #return non expired public keys in JWKS format
    valid_keys = get_valid_keys()
    return jsonify({"keys": [key_to_jwk(key) for key in valid_keys]})


@app.route("/auth", methods=["POST"]) #return a JWT signed by valid db backed key
def auth():
    expired_requested = "expired" in request.args
    key = get_signing_key(expired=expired_requested)

    if expired_requested:
        issued_at = key["expires_at"] - 3600
    else:
        issued_at = int(time.time())

    payload = {
        "sub": "fake-user",
        "iat": issued_at,
        "exp": key["expires_at"],
    }

    token = jwt.encode(
        payload,
        key["private_key"],
        algorithm="RS256",
        headers={"kid": str(key["kid"])},
    )

    return token


if __name__ == "__main__":
    app.run(port=8080)
