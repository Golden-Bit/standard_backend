from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Dict

# Dizionario per mantenere le connessioni ai database
databases: Dict[str, AsyncIOMotorClient] = {}


# Modello per le credenziali del database

# Funzione per ottenere un client MongoDB
async def get_mongo_client(username: str = None, password: str = None, host: str = "localhost", port: int = 27017):
    uri = f"mongodb://{username}:{password}@{host}:{port}/?maxPoolSize=10" if username and password else \
        f"mongodb://{host}:{port}/?maxPoolSize=10"
    return AsyncIOMotorClient(uri)


# Funzione per aggiungere un nuovo database
async def add_database(db_name: str, username: str = None, password: str = None, host: str = "localhost", port: int = 27017):
    client = await get_mongo_client(username, password, host, port)
    database = client[db_name]
    databases[db_name] = database
    return database


# Funzione per ottenere un'istanza di database esistente
def get_db_instance(db_name: str):
    if db_name in databases:
        return databases[db_name]
    else:
        raise ValueError(f"Database '{db_name}' not found. Please create it first.")