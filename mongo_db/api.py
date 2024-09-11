from typing import List, Optional, Literal
import os
import yaml
from fastapi import FastAPI, HTTPException, status, UploadFile, File, Body
from typing import Any, Dict
from pydantic import BaseModel, ValidationError, create_model, Field
from bson import ObjectId
from mongo_db.utils import add_database, get_mongo_client, get_db_instance, validate_input, schemas

app = FastAPI(
    title="MongoDB FastAPI Backend",
    description="API per la gestione di database MongoDB, collezioni e documenti utilizzando FastAPI.",
    version="1.0.0",
)

# Dizionario globale per mantenere le connessioni ai database
databases = {}


class DBCredentials(BaseModel):
    """Modello per le credenziali di accesso al database."""
    db_name: str
    username: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = "localhost"
    port: Optional[int] = 27017


# Modello per la query di ricerca
class SearchQuery(BaseModel):
    field: str
    value: Any
    exact_match: Optional[bool] = True


@app.post("/create_database/", summary="Crea un nuovo database", response_description="Il database è stato creato con successo")
async def create_database(credentials: DBCredentials):
    """
    Crea un nuovo database e lo connette.

    - **db_name**: Nome del database
    - **username**: Username per l'autenticazione
    - **password**: Password per l'autenticazione
    - **host**: Host del database
    - **port**: Porta del database
    """
    try:
        db = await add_database(credentials.db_name, credentials.username, credentials.password, credentials.host, credentials.port)
        return {"message": f"Database '{credentials.db_name}' created and connected successfully."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nella creazione del database: {str(e)}")


@app.get("/list_databases/", summary="Ottieni l'elenco dei database", response_description="Elenco dei database esistenti")
async def list_databases():
    """
    Recupera l'elenco di tutti i database esistenti sul server MongoDB.
    """
    try:
        client = await get_mongo_client()
        db_list = await client.list_database_names()
        return {"databases": db_list}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nel recupero dei database: {str(e)}")


@app.delete("/delete_database/{db_name}/", summary="Elimina un database esistente", response_description="Il database è stato eliminato con successo")
async def delete_database(db_name: str):
    """
    Elimina un database esistente.

    - **db_name**: Nome del database da eliminare
    """
    try:
        client = await get_mongo_client()
        await client.drop_database(db_name)
        databases.pop(db_name, None)  # Rimuovi il database dal dizionario se esiste
        return {"message": f"Database '{db_name}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nell'eliminazione del database: {str(e)}")


@app.post("/{db_name}/create_collection/", summary="Crea una nuova collezione", response_description="La collezione è stata creata con successo")
async def create_collection(db_name: str, collection_name: str):

    """
    Crea una nuova collezione all'interno di un database esistente.

    - **db_name**: Nome del database
    - **collection_name**: Nome della collezione da creare
    """

    try:
        db = get_db_instance(db_name)
    except ValueError:
        db = await add_database(db_name)

    try:
        await db.create_collection(collection_name)
        return {"message": f"Collection '{collection_name}' created successfully in database '{db_name}'."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nella creazione della collezione: {str(e)}")


@app.get("/{db_name}/list_collections/", summary="Elenca le collezioni in un database", response_description="Elenco delle collezioni presenti nel database")
async def list_collections(db_name: str):
    """
    Recupera l'elenco di tutte le collezioni in un database specifico.

    - **db_name**: Nome del database
    """

    try:
        db = get_db_instance(db_name)
    except ValueError:
        db = await add_database(db_name)

    try:
        #db = get_db_instance(db_name)
        collection_list = await db.list_collection_names()
        return {"collections": collection_list}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nel recupero delle collezioni: {str(e)}")


@app.delete("/{db_name}/delete_collection/{collection_name}/", summary="Elimina una collezione esistente", response_description="La collezione è stata eliminata con successo")
async def delete_collection(db_name: str, collection_name: str):
    """
    Elimina una collezione esistente in un database specifico.

    - **db_name**: Nome del database
    - **collection_name**: Nome della collezione da eliminare
    """
    try:
        db = get_db_instance(db_name)
        await db.drop_collection(collection_name)
        return {"message": f"Collection '{collection_name}' deleted successfully from database '{db_name}'."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nell'eliminazione della collezione: {str(e)}")


# Funzione per caricare e associare schemi YAML alle collezioni
@app.post("/upload_schema/{db_name}/{collection_name}/",
          summary="Carica uno o più schemi YAML per una collezione specifica")
async def upload_schema(db_name: str, collection_name: str, files: List[UploadFile] = File(...)):
    try:
        schema_dir = os.path.join("allowed_schemas", db_name, collection_name)
        os.makedirs(schema_dir, exist_ok=True)

        for file in files:
            content = await file.read()
            schema = yaml.safe_load(content)

            # Salva lo schema nella directory specifica
            schema_path = os.path.join(schema_dir, file.filename)
            with open(schema_path, "w") as schema_file:
                yaml.dump(schema, schema_file)

            # Aggiorna il dizionario degli schemi caricati
            schema_key = f"{db_name}/{collection_name}/{file.filename}"
            schemas[schema_key] = schema

        return {
            "message": f"Schemi per la collezione '{collection_name}' nel database '{db_name}' caricati con successo."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore durante il caricamento degli schemi: {str(e)}")


@app.post("/{db_name}/{collection_name}/add_item/",
          summary="Aggiungi un documento in una collezione convalidato tramite schema specifico")
async def add_item(db_name: str, collection_name: str, data: Dict[str, Any]):
    """
    Aggiungi un nuovo documento in una collezione esistente, convalidato tramite uno schema YAML specifico.

    - **db_name**: Nome del database
    - **collection_name**: Nome della collezione
    - **data**: Dati del documento da inserire
    """

    try:
        db = get_db_instance(db_name)
    except ValueError:
        db = await add_database(db_name)

    try:
        validated_data = validate_input(db_name, collection_name, data)
        #db = get_db_instance(db_name)
        collection = db[collection_name]
        result = await collection.insert_one(validated_data)
        return {"message": "Item added successfully.", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore nell'aggiunta del documento: {str(e)}")


# Endpoint esistente per la creazione di un database
@app.post("/create_database/", summary="Crea un nuovo database", response_description="Il database è stato creato con successo")
async def create_database(credentials: DBCredentials):
    try:
        db = await add_database(credentials.db_name, credentials.username, credentials.password, credentials.host, credentials.port)
        return {"message": f"Database '{credentials.db_name}' created and connected successfully."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nella creazione del database: {str(e)}")


@app.post("/{db_name}/get_items/{collection_name}/", summary="Recupera tutti i documenti di una collezione", response_description="Elenco dei documenti nella collezione", response_model=List[Dict[str, Any]])
async def get_items(db_name: str, collection_name: str, filter: Optional[Dict[str, Any]] = Body(None)):
    """
    Recupera tutti i documenti di una collezione specifica, con la possibilità di applicare un filtro.

    - **db_name**: Nome del database
    - **collection_name**: Nome della collezione
    - **filter**: (Opzionale) Filtro per limitare i documenti restituiti
    """

    try:
        db = get_db_instance(db_name)
    except ValueError:
        db = await add_database(db_name)

    query = filter if filter else {}
    try:
        #db = get_db_instance(db_name)
        collection = db[collection_name]
        items = []
        async for item in collection.find(query):
            item["_id"] = str(item["_id"])
            items.append(item)
        return items
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nel recupero dei documenti: {str(e)}")


@app.put("/{db_name}/update_item/{collection_name}/{item_id}/", summary="Aggiorna un documento in una collezione", response_description="Il documento è stato aggiornato con successo")
async def update_item(db_name: str, collection_name: str, item_id: str, item: Dict[str, Any]):
    """
    Aggiorna un documento esistente in una collezione.

    - **db_name**: Nome del database
    - **collection_name**: Nome della collezione
    - **item_id**: ID del documento da aggiornare
    - **item**: Nuovi dati del documento
    """

    try:
        db = get_db_instance(db_name)
    except ValueError:
        db = await add_database(db_name)

    try:
        #db = get_db_instance(db_name)
        collection = db[collection_name]
        result = await collection.update_one({"_id": ObjectId(item_id)}, {"$set": item})
        if result.modified_count:
            return {"message": "Item updated successfully."}
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nessun documento aggiornato.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nell'aggiornamento del documento: {str(e)}")


@app.delete("/{db_name}/delete_item/{collection_name}/{item_id}/", summary="Elimina un documento in una collezione", response_description="Il documento è stato eliminato con successo")
async def delete_item(db_name: str, collection_name: str, item_id: str):
    """
    Elimina un documento esistente in una collezione.

    - **db_name**: Nome del database
    - **collection_name**: Nome della collezione
    - **item_id**: ID del documento da eliminare
    """

    try:
        db = get_db_instance(db_name)
    except ValueError:
        db = await add_database(db_name)

    try:
        #db = get_db_instance(db_name)
        collection = db[collection_name]
        result = await collection.delete_one({"_id": ObjectId(item_id)})
        if result.deleted_count:
            return {"message": "Item deleted successfully."}
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento non trovato.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nell'eliminazione del documento: {str(e)}")


# Endpoint per recuperare un documento specifico in un database specifico
@app.get("/{db_name}/get_item/{collection_name}/{item_id}/", summary="Recupera un documento specifico", response_description="Il documento è stato recuperato con successo", response_model=Dict[str, Any])
async def get_item(db_name: str, collection_name: str, item_id: str):
    """
    Recupera un documento specifico in una collezione.

    - **db_name**: Nome del database
    - **collection_name**: Nome della collezione
    - **item_id**: ID del documento da recuperare
    """

    try:
        db = get_db_instance(db_name)
    except ValueError:
        db = await add_database(db_name)

    try:
        #db = get_db_instance(db_name)
        collection = db[collection_name]
        item = await collection.find_one({"_id": ObjectId(item_id)})
        if item:
            item["_id"] = str(item["_id"])
            return item
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento non trovato.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nel recupero del documento: {str(e)}")


@app.get("/get_schemas/{db_name}/{collection_name}/", summary="Visualizza gli schemi associati a una collezione", response_description="Elenco degli schemi YAML per la collezione specificata")
async def get_schemas(db_name: str, collection_name: str):
    """
    Recupera gli schemi YAML associati a una specifica collezione in un database.

    - **db_name**: Nome del database
    - **collection_name**: Nome della collezione
    """
    try:
        schema_dir = os.path.join("allowed_schemas", db_name, collection_name)
        if not os.path.exists(schema_dir):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nessuno schema trovato per questa collezione e database.")

        schema_files = os.listdir(schema_dir)
        if not schema_files:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nessuno schema trovato per questa collezione e database.")

        schemas_content = {}
        for schema_file in schema_files:
            schema_path = os.path.join(schema_dir, schema_file)
            with open(schema_path, "r") as f:
                schema_content = yaml.safe_load(f)
                schemas_content[schema_file] = schema_content

        return {"schemas": schemas_content}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore nel recupero degli schemi: {str(e)}")


# Codice per eseguire l'applicazione
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
