import yaml
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Dict, Any, Literal
from pydantic import BaseModel, ValidationError, create_model, Field
from fastapi import FastAPI, HTTPException, status, UploadFile, File
import os

# Dizionario per tenere traccia degli schemi caricati
schemas: Dict[str, Dict[str, Any]] = {}

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




def create_pydantic_model(schema_name: str, schema: Dict[str, Any]):
    """
    Crea un modello Pydantic dinamico basato su uno schema YAML.
    """
    fields = {}
    for field_name, field_props in schema.items():
        field_type = eval(field_props['type'])  # Converti il tipo di dato da stringa a tipo Python
        field_args = {}

        if 'title' in field_props:
            field_args['title'] = field_props['title']
        if 'min_length' in field_props:
            field_args['min_length'] = field_props['min_length']
        if 'max_length' in field_props:
            field_args['max_length'] = field_props['max_length']
        if 'default' in field_props:
            field_args['default'] = field_props['default']
        if 'ge' in field_props:  # greater than or equal
            field_args['ge'] = field_props['ge']
        if 'le' in field_props:  # less than or equal
            field_args['le'] = field_props['le']
        if 'enum' in field_props:
            field_type = Literal[tuple(field_props['enum'])]  # Enum support

        fields[field_name] = (field_type, Field(**field_args))

    return create_model(schema_name, **fields)


def validate_input(db_name: str, collection_name: str, data: Dict[str, Any]):
    schema_dir = os.path.join("allowed_schemas", db_name, collection_name)
    if not os.path.exists(schema_dir) or not os.listdir(schema_dir):
        # Se non ci sono schemi, accetta qualsiasi input
        return data

    schema_files = os.listdir(schema_dir)
    for schema_file in schema_files:
        schema_key = f"{db_name}/{collection_name}/{schema_file}"
        if schema_key not in schemas:
            with open(os.path.join(schema_dir, schema_file), "r") as f:
                schemas[schema_key] = yaml.safe_load(f)

        schema = schemas[schema_key]
        try:
            # Crea un modello Pydantic dinamico basato sullo schema YAML
            dynamic_model = create_pydantic_model(schema_file, schema)
            validated_data = dynamic_model(**data)
            return validated_data.dict()
        except ValidationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore di validazione: {e.errors()}")

    # Se nessun schema corrisponde, accetta qualsiasi input
    return data