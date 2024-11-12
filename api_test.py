import requests

# Configurazione dell'URL dell'API
BASE_URL = "https://teatek-llm.theia-innovation.com/api/user-backend"
REGISTER_ENDPOINT = "/register/"
LOGIN_ENDPOINT = "/login/"

# Dati per registrazione e login
registration_data = {
    "username": "testuser",
    "email": "testuser@example.com",
    "hashed_password": "TestPassword123!"
}

login_data = {
    "username": "testuser",
    "password": "TestPassword123!"
}

# Funzione per registrare un nuovo utente
def register_user():
    try:
        print("[INFO] Registrando utente...")
        response = requests.post(
            BASE_URL + REGISTER_ENDPOINT,
            json=registration_data,
            headers={"Content-Type": "application/json"}
        )
        print("Status Code:", response.status_code)
        if response.status_code == 200:
            print("Registrazione avvenuta con successo!")
            print("Response JSON:", response.json())
        else:
            print("Errore durante la registrazione:", response.json())
    except requests.exceptions.RequestException as e:
        print("Errore di rete durante la registrazione:", e)

# Funzione per effettuare il login
def login_user():
    try:
        print("[INFO] Effettuando il login...")
        response = requests.post(
            BASE_URL + LOGIN_ENDPOINT,
            data=login_data,  # OAuth2 richiede i dati nel formato application/x-www-form-urlencoded
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        print("Status Code:", response.status_code)
        if response.status_code == 200:
            print("Login avvenuto con successo!")
            print("JWT Token:", response.json().get("access_token"))
        else:
            print("Errore durante il login:", response.json())
    except requests.exceptions.RequestException as e:
        print("Errore di rete durante il login:", e)

# Esegui i test
if __name__ == "__main__":
    register_user()
    login_user()
