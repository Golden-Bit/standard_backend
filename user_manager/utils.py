from fastapi import FastAPI, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Union, Any, Dict
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
import requests
from datetime import datetime, timedelta
import os


# Configurazione per il sistema di sicurezza
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# URL del servizio MongoDB
MONGO_SERVICE_URL = "http://127.0.0.1:8000"


# Modello per i permessi
class Permission(BaseModel):
    code: str = Field(..., title="Codice Permesso", description="Codice univoco che rappresenta il permesso dell'utente.")
    description: Optional[str] = Field(None, title="Descrizione Permesso", description="Descrizione facoltativa del permesso.")

    class Config:
        json_schema_extra = {
            "example": {
                "code": "admin_access",
                "description": "Accesso completo alle funzionalità amministrative"
            }
        }


# Modello per le relazioni tra utenti
class UserRelation(BaseModel):
    username: str = Field(..., title="Username", description="Username dell'utente gestito o manager.")
    email: EmailStr = Field(..., title="Email", description="Email dell'utente gestito o manager.")
    permissions: List[Permission] = Field([], title="Permessi", description="Lista dei permessi assegnati all'utente.")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "user123",
                "email": "user123@example.com",
                "permissions": [{"code": "read_access", "description": "Accesso in sola lettura"}]
            }
        }


# Modello Utente
class User(BaseModel):
    username: str = Field(..., title="Username", description="Nome utente unico per l'autenticazione.")
    email: EmailStr = Field(..., title="Email", description="Email associata all'account dell'utente.")
    full_name: Optional[str] = Field(None, title="Nome Completo", description="Nome completo dell'utente.")
    disabled: Optional[bool] = Field(False, title="Disabilitato", description="Indica se l'account utente è disabilitato.")
    managed_users: Optional[List[UserRelation]] = Field([], title="Utenti Gestiti", description="Lista degli utenti gestiti da questo utente.")
    manager_users: Optional[List[UserRelation]] = Field([], title="Manager", description="Lista dei manager di questo utente.")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "admin123",
                "email": "admin123@example.com",
                "full_name": "Admin User",
                "disabled": False,
                "managed_users": [],
                "manager_users": []
            }
        }


class UserInDB(User):
    id: str = Field("", alias="_id", title="ID Utente", description="ID univoco dell'utente nel database.")
    hashed_password: str = Field(..., title="Password Hashata", description="Password dell'utente in forma hashata per sicurezza.")
    databases: Optional[List[Dict[str, Union[str, int]]]] = Field([], title="Databases", description="Lista dei database creati dall'utente.")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "admin123",
                "email": "admin123@example.com",
                "full_name": "Admin User",
                "hashed_password": "password1234",
                "disabled": False,
                "managed_users": [],
                "manager_users": []
            }
        }

class Token(BaseModel):
    access_token: str = Field(..., title="Token di Accesso", description="Token di accesso JWT.")
    token_type: str = Field(..., title="Tipo di Token", description="Tipo di token di autenticazione.")
    refresh_token: Optional[str] = Field(None, title="Token di Refresh", description="Token di refresh JWT.")


class TokenData(BaseModel):
    username: Optional[str] = Field(None, title="Username", description="Nome utente estratto dal token JWT.")


class TokenInDB(BaseModel):
    username: str = Field(..., title="Username", description="Nome utente associato al token.")
    token: str = Field(..., title="Token", description="Il token JWT.")
    token_type: str = Field(..., title="Tipo di Token", description="Tipo di token, es. access_token o refresh_token.")
    expires_at: str = Field(..., title="Data di Scadenza", description="Data e ora di scadenza del token in formato ISO 8601.")


class UserDeleteRequest(BaseModel):
    username: str = Field(..., title="Username", description="Nome utente da eliminare.")
    email: EmailStr = Field(..., title="Email", description="Email associata all'utente.")
    password: str = Field(..., title="Password", description="Password attuale dell'utente per confermare l'eliminazione.")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "admin123",
                "email": "admin123@example.com",
                "password": "password123"
            }
        }


class PasswordChangeRequest(BaseModel):
    username: str = Field(..., title="Username", description="Nome utente dell'account.")
    old_password: str = Field(..., title="Vecchia Password", description="Vecchia password dell'utente.")
    new_password: str = Field(..., title="Nuova Password", description="Nuova password desiderata dall'utente.")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "user123",
                "old_password": "oldpassword123",
                "new_password": "newpassword456"
            }
        }


class DatabaseCreationRequest(BaseModel):
    db_name: str = Field(..., title="Nome del Database", description="Nome del database da creare.")


# Funzioni di utilità per la gestione degli utenti
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    refresh_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return refresh_jwt


def store_token_in_db(username: str, token: Union[str, Any], token_type: str, expires_at: datetime):
    if not isinstance(token, str):
        token = str(token)
    token_data = TokenInDB(
        username=username,
        token=token,
        token_type=token_type,
        expires_at=str(expires_at.isoformat())
    )
    response = requests.post(f"{MONGO_SERVICE_URL}/database/tokens_collection/add_item", json=token_data.dict())
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Errore durante la memorizzazione del token")


def revoke_token_in_db(token: Union[str, Any]):
    if not isinstance(token, str):
        token = str(token)
    filter_data = {"token": token}
    response = requests.delete(f"{MONGO_SERVICE_URL}/database/tokens_collection/delete_item", json=filter_data)
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Errore durante la revoca del token")


def get_token_from_db(token: Union[str, Any]) -> Optional[TokenInDB]:
    if not isinstance(token, str):
        token = str(token)
    filter_data = {"token": token}
    response = requests.post(f"{MONGO_SERVICE_URL}/database/get_items/tokens_collection", json=filter_data)
    if response.status_code == 200 and response.json():
        token_data = response.json()[-1]  # Assuming only one token will match
        return TokenInDB(**token_data)
    return None


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)

        # Check if the token is revoked
        stored_token = get_token_from_db(token)
        if not stored_token or datetime.fromisoformat(stored_token.expires_at) < datetime.utcnow():
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Using a POST request with a filter in the body to get the specific user
    filter_data = {"username": token_data.username}
    response = requests.post(f"{MONGO_SERVICE_URL}/database/get_items/users_collection/", json=filter_data)

    if response.status_code != 200 or not response.json():
        raise credentials_exception

    user = response.json()[-1]  # Assuming only one user will match the username

    return UserInDB(**user)
