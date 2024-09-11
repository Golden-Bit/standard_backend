from fastapi import FastAPI, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Union, Any, Dict
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
import requests
from datetime import datetime, timedelta
import os
from fastapi.middleware.cors import CORSMiddleware
from user_manager import mongodb_route
from user_manager.utils import UserInDB, MONGO_SERVICE_URL, get_password_hash, Token, verify_password, \
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, create_access_token, create_refresh_token, \
    store_token_in_db, UserDeleteRequest, get_current_user, SECRET_KEY, ALGORITHM, get_token_from_db, oauth2_scheme, \
    revoke_token_in_db, User, PasswordChangeRequest, DatabaseCreationRequest

# Configurazione FastAPI
app = FastAPI(
    title="User Management Service",
    description="""
## Servizio per la gestione degli utenti
Include funzionalità di autenticazione, autorizzazione e gestione delle relazioni tra utenti.
### Funzionalità:
* Registrazione utente
* Autenticazione tramite OAuth2
* Gestione dei token di accesso e di refresh
* Visualizzazione e gestione degli utenti gestiti
* Eliminazione account
""",
    version="1.0.0",
)


# Configurazione CORS per permettere tutte le origini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permetti tutte le origini
    allow_credentials=True,
    allow_methods=["*"],  # Permetti tutti i metodi (GET, POST, OPTIONS, ecc.)
    allow_headers=["*"],  # Permetti tutti gli headers
)

@app.post("/register/", summary="Register a new user", response_description="User registered successfully")
def register_user(user: UserInDB):
    """
    ### Endpoint per registrare un nuovo utente

    **Parametri:**
    - **user**: Un oggetto JSON che rappresenta i dettagli dell'utente da registrare

    **Ritorna:**
    - Messaggio di conferma della registrazione

    **Eccezioni:**
    - `400 Bad Request`: Se l'username o l'email già esistono.
    - `500 Internal Server Error`: Se si verifica un errore durante la registrazione.
    """
    # Ensure uniqueness of username and email
    username_filter = {"username": user.username}
    email_filter = {"email": user.email}
    username_response = requests.post(f"{MONGO_SERVICE_URL}/database/get_items/users_collection/", json=username_filter)
    email_response = requests.post(f"{MONGO_SERVICE_URL}/database/get_items/users_collection/", json=email_filter)

    if username_response.status_code == 200 and username_response.json():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    if email_response.status_code == 200 and email_response.json():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    hashed_password = get_password_hash(user.hashed_password)

    # Sovrascrivi i valori di `manager_users`, `managed_users`, e `databases`
    user_in_db = user.dict()
    user_in_db["hashed_password"] = hashed_password
    user_in_db["managed_users"] = []
    user_in_db["manager_users"] = []
    user_in_db["databases"] = []

    response = requests.post(f"{MONGO_SERVICE_URL}/database/users_collection/add_item", json=user_in_db)

    if response.status_code != 200:
        print(response.__dict__)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error registering user")

    return {"message": "User registered successfully"}


@app.post("/login/", response_model=Token, summary="Autentica un utente")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    ### Endpoint per autenticare un utente e ottenere i token di accesso e refresh

    **Parametri:**
    - **form_data**: Dati del form di autenticazione (username e password).

    **Ritorna:**
    - Un oggetto JSON contenente il `token di accesso` e il `token di refresh`.

    **Eccezioni:**
    - `401 Unauthorized`: Se le credenziali fornite sono errate.
    """
    # Creating the filter data to find the user by username
    filter_data = {"username": form_data.username}

    # Sending a POST request with the filter to find the user
    response = requests.post(f"{MONGO_SERVICE_URL}/database/get_items/users_collection/", json=filter_data)

    if response.status_code != 200 or not response.json():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    user = response.json()[-1]  # Assuming only one user will match the username

    user_in_db = UserInDB(**user)

    # Verifying the password
    if not verify_password(form_data.password, user_in_db.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Creating the access token and refresh token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    access_token = create_access_token(data={"sub": user_in_db.username}, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(data={"sub": user_in_db.username}, expires_delta=refresh_token_expires)

    # Store the tokens in the database
    store_token_in_db(user_in_db.username, access_token, "access_token", datetime.utcnow() + access_token_expires)
    store_token_in_db(user_in_db.username, refresh_token, "refresh_token", datetime.utcnow() + refresh_token_expires)

    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@app.delete("/users_collection/me/delete", summary="Elimina l'utente", response_description="Utente eliminato con successo")
def delete_user(delete_request: UserDeleteRequest, current_user: UserInDB = Depends(get_current_user)):
    """
    ### Endpoint per eliminare un utente

    **Parametri:**
    - **delete_request**: Dati di conferma per l'eliminazione (username, email e password).

    **Ritorna:**
    - Messaggio di conferma dell'eliminazione dell'utente.

    **Eccezioni:**
    - `400 Bad Request`: Se l'username o l'email non corrispondono.
    - `401 Unauthorized`: Se la password è errata.
    - `500 Internal Server Error`: Se si verifica un errore durante l'eliminazione.
    """
    # Verifica che l'username e l'email corrispondano a quelli dell'utente corrente
    if delete_request.username != current_user.username or delete_request.email != current_user.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username o email non corrispondono")

    # Verifica la password
    if not verify_password(delete_request.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password non corretta")

    # Rimuovi l'utente dal database
    response = requests.delete(f"{MONGO_SERVICE_URL}/database/delete_item/users_collection/{current_user.id}")
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Errore durante l'eliminazione dell'utente")

    return {"message": "Utente eliminato con successo"}


@app.post("/refresh_token/", summary="Rinnova il token di accesso", response_description="Token di accesso rinnovato con successo")
def refresh_access_token(refresh_token: str):
    """
    ### Endpoint per rinnovare il token di accesso utilizzando il token di refresh

    **Parametri:**
    - **refresh_token**: Il token di refresh dell'utente.

    **Ritorna:**
    - Un nuovo `token di accesso`.

    **Eccezioni:**
    - `401 Unauthorized`: Se il token di refresh è scaduto o non valido.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        stored_refresh_token = get_token_from_db(refresh_token)
        if not stored_refresh_token or datetime.fromisoformat(stored_refresh_token.expires_at) < datetime.utcnow():
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Create new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": username}, expires_delta=access_token_expires)

    # Store the new access token in the database
    store_token_in_db(username, access_token, "access_token", datetime.utcnow() + access_token_expires)

    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/logout/", summary="Logout utente", response_description="Logout eseguito con successo")
def logout_user(current_user: UserInDB = Depends(get_current_user)):
    """
    ### Endpoint per eseguire il logout di un utente

    **Ritorna:**
    - Messaggio di conferma del logout.

    **Eccezioni:**
    - `500 Internal Server Error`: Se si verifica un errore durante il logout.
    """
    # Revoke access and refresh tokens
    access_token = Depends(oauth2_scheme)  # Problema qui
    stored_access_token = get_token_from_db(access_token)
    if stored_access_token:
        revoke_token_in_db(stored_access_token.token)

    stored_refresh_token = get_token_from_db(current_user.username)
    if stored_refresh_token:
        revoke_token_in_db(stored_refresh_token.token)

    return {"message": "Logout eseguito con successo"}


@app.get("/users_collection/me/", summary="Recupera il profilo utente", response_description="Profilo utente recuperato con successo")
def read_users_me(current_user: User = Depends(get_current_user)):
    """
    ### Endpoint per recuperare il profilo dell'utente corrente

    **Ritorna:**
    - Oggetto JSON che rappresenta il profilo utente.
    """
    return current_user


@app.get("/users_collection/me/managed_users/", summary="Recupera gli utenti gestiti dall'utente corrente", response_description="Utenti gestiti recuperati con successo")
def get_managed_users(current_user: UserInDB = Depends(get_current_user)):
    """
    ### Endpoint per recuperare la lista degli utenti gestiti dall'utente corrente

    **Ritorna:**
    - Lista di oggetti JSON che rappresentano gli utenti gestiti, includendo solo le informazioni di `username`, `email`, e `full_name`.
    """
    filter_data = {"username": {"$in": [u["username"] for u in current_user.managed_users]}}
    response = requests.post(f"{MONGO_SERVICE_URL}/database/get_items/users_collection/", json=filter_data)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Errore nel recupero degli utenti gestiti")

    managed_users_info = [
        {
            "username": user["username"],
            "email": user["email"],
            "full_name": user.get("full_name", "")
        }
        for user in response.json()
    ]

    return managed_users_info


@app.put("/users_collection/me/", summary="Aggiorna il profilo utente", response_description="Profilo utente aggiornato con successo")
def update_user_me(user_update: User, current_user: UserInDB = Depends(get_current_user)):
    """
    ### Endpoint per aggiornare il profilo dell'utente corrente

    **Parametri:**
    - **user_update**: Oggetto JSON con i campi aggiornati dell'utente.

    **Ritorna:**
    - Messaggio di conferma dell'aggiornamento del profilo.

    **Eccezioni:**
    - `400 Bad Request`: Se si verifica un errore durante l'aggiornamento.
    """
    # Evita che l'utente modifichi `username`, `password`, `managed_users`, `manager_users`, e `databases`
    immutable_fields = {"username", "hashed_password", "managed_users", "manager_users", "databases"}
    updated_user = {k: v for k, v in user_update.dict().items() if v is not None and k not in immutable_fields}

    # Send the updated data to the MongoDB API
    response = requests.put(f"{MONGO_SERVICE_URL}/database/update_item/users_collection/{current_user.id}/",
                            json=updated_user)

    # Check for errors in the response
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Errore nell'aggiornamento del profilo")

    return {"message": "Profile updated successfully"}


@app.put("/users_collection/me/change_password/", summary="Cambia la password dell'utente",
         response_description="Password cambiata con successo")
def change_user_password(password_change_request: PasswordChangeRequest,
                         current_user: UserInDB = Depends(get_current_user)):
    """
    ### Endpoint per cambiare la password dell'utente

    **Parametri:**
    - **password_change_request**: Dati necessari per cambiare la password (username, vecchia password e nuova password).

    **Ritorna:**
    - Messaggio di conferma del cambio password.

    **Eccezioni:**
    - `400 Bad Request`: Se l'username non corrisponde a quello dell'utente corrente.
    - `401 Unauthorized`: Se la vecchia password è errata.
    - `500 Internal Server Error`: Se si verifica un errore durante l'aggiornamento della password.
    """
    # Verifica che l'username corrisponda a quello dell'utente corrente
    if password_change_request.username != current_user.username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username non corrisponde")

    # Verifica la vecchia password
    if not verify_password(password_change_request.old_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vecchia password non corretta")

    # Hash della nuova password
    new_hashed_password = get_password_hash(password_change_request.new_password)

    # Aggiorna la password nel database
    response = requests.put(
        f"{MONGO_SERVICE_URL}/database/update_item/users_collection/{current_user.id}/",
        json={"hashed_password": new_hashed_password}
    )

    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Errore durante il cambio della password")

    # Invalida tutti i token dell'utente corrente
    try:
        # Recupera tutti i token di accesso e refresh dell'utente corrente
        stored_access_token = get_token_from_db(current_user.username)
        stored_refresh_token = get_token_from_db(current_user.username)

        if stored_access_token:
            revoke_token_in_db(stored_access_token.token)

        if stored_refresh_token:
            revoke_token_in_db(stored_refresh_token.token)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Errore durante l'invalidazione dei token")

    return {"message": "Password cambiata con successo e tutti i token sono stati invalidati"}


# Include le rotte del MongoDB
app.include_router(mongodb_route.router)


# Codice per eseguire l'applicazione
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8101, reload=False)
