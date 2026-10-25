# JWKS Server

A Flask-based JWKS server that generates RSA keys, stores private keys in SQLite, issues signed JWTs, and exposes public keys through a JWKS endpoint.

## Features

- RSA key generation
- SQLite-backed private key storage
- Persistent keys across server restarts
- RS256 JWT signing
- Valid and expired JWT generation
- JWKS endpoint for public key discovery
- Parameterized SQL queries
- Automated tests with pytest
- Test coverage support with pytest-cov

## Requirements

- Python 3
- Flask
- PyJWT
- cryptography
- pytest
- pytest-cov

Install dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Database

The application creates a SQLite database named:

```text
totally_not_my_privateKeys.db
```

The database contains a `keys` table with the following schema:

```sql
CREATE TABLE IF NOT EXISTS keys(
    kid INTEGER PRIMARY KEY AUTOINCREMENT,
    key BLOB NOT NULL,
    exp INTEGER NOT NULL
)
```

Each row contains:

- `kid` - unique key identifier
- `key` - serialized RSA private key stored as PEM bytes
- `exp` - key expiration time stored as a Unix timestamp

The database is created automatically when the application starts.

## Key Storage

RSA private keys cannot be stored directly as Python objects in SQLite.

Before a key is stored, it is serialized into PEM format. When the key is retrieved from the database, the PEM data is deserialized back into an RSA private key object.

This allows the application to persist private keys while still being able to use them for JWT signing.

## API

### `GET /.well-known/jwks.json`

Returns all currently valid public keys in JWKS format.

Example response:

```json
{
  "keys": [
    {
      "kty": "RSA",
      "kid": "1",
      "use": "sig",
      "alg": "RS256",
      "n": "...",
      "e": "AQAB"
    }
  ]
}
```

Expired keys are not included in the JWKS response.

### `POST /auth`

Returns a JWT signed with a currently valid RSA private key.

```text
POST /auth
```

### `POST /auth?expired=true`

Returns a JWT signed using an expired RSA private key.

```text
POST /auth?expired=true
```

The authentication endpoint is intentionally mocked and does not perform real user authentication.

## Running the Server

Run the application with:

```bash
python app.py
```

By default, the server runs on:

```text
http://127.0.0.1:8080
```

## Testing

Run the test suite with:

```bash
python -m pytest
```

Run the tests with coverage:

```bash
python -m pytest --cov=. --cov-report=term-missing
```

The test suite covers the authentication endpoint, expired JWT behavior, JWKS output, and database-backed key storage.

## SQL Injection Prevention

Database queries use SQLite query parameters rather than inserting values directly into SQL strings.

For example:

```python
connection.execute(
    "SELECT kid, key, exp FROM keys WHERE exp > ?",
    (current_time,),
)
```

Using parameterized queries separates SQL code from values and helps prevent SQL injection vulnerabilities.

## Project Structure

```text
.
├── app.py
├── keys.py
├── test_app.py
├── requirements.txt
├── README.md
└── .gitignore
```

The SQLite database is generated at runtime and should not be committed to source control.

## License

This project was created for educational purposes.
