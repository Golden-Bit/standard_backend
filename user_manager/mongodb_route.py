from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests

from user_manager.utils import UserInDB, get_current_user

# URL del servizio MongoDB
MONGO_SERVICE_URL = "http://127.0.0.1:8000"

router = APIRouter(
    prefix="/mongo",
    tags=["MongoDB Management"],
    responses={404: {"description": "Not found"}},
)


# Modello per la creazione del database
class DatabaseCreationRequest(BaseModel):
    db_name: str


# Funzione per verificare se il database appartiene all'utente corrente
def verify_user_database(db_name: str, current_user: UserInDB):
    if not any(db["db_name"] == db_name for db in current_user.databases):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Non sei autorizzato ad accedere a questo database."
        )


@router.post("/create_user_database/", summary="Crea un nuovo database MongoDB con le proprie credenziali",
             response_description="Database creato con successo")
async def create_user_database(request: DatabaseCreationRequest, current_user: UserInDB = Depends(get_current_user)):
    """
    ### Crea un nuovo database MongoDB utilizzando le proprie credenziali.
    """
    username = current_user.username
    prefixed_db_name = f"{username}-{request.db_name}"
    host = "localhost"
    port = 27017

    try:
        # Creazione del database tramite l'API
        db_credentials = {
            "db_name": prefixed_db_name,
            "host": host,
            "port": port
        }
        response = requests.post(f"{MONGO_SERVICE_URL}/create_database/", json=db_credentials)

        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Errore durante la creazione del database")

        # Verifica se esiste già un database con lo stesso nome e host
        database_exists = any(db["db_name"] == prefixed_db_name and db["host"] == host for db in current_user.databases)

        if not database_exists:
            # Se il database non esiste già nella lista, aggiungilo
            new_database_info = {
                "db_name": prefixed_db_name,
                "host": host,
                "port": port
            }
            current_user.databases.append(new_database_info)

            update_response = requests.put(
                f"{MONGO_SERVICE_URL}/database/update_item/users_collection/{current_user.id}/",
                json={"databases": current_user.databases}
            )

            if update_response.status_code != 200:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Errore durante l'aggiornamento delle informazioni dell'utente")

        return {"message": f"Database '{prefixed_db_name}' creato con successo."}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Errore durante la creazione del database: {str(e)}")



@router.get("/list_databases/", summary="Ottieni l'elenco dei database dell'utente",
            response_description="Elenco dei database esistenti")
async def list_databases(current_user: UserInDB = Depends(get_current_user)):
    """
    Recupera l'elenco dei database esistenti associati all'utente.
    """
    return {"databases": current_user.databases}


@router.post("/{db_name}/create_collection/", summary="Crea una nuova collezione",
             response_description="La collezione è stata creata con successo")
async def create_collection(db_name: str, collection_name: str, current_user: UserInDB = Depends(get_current_user)):
    """
    Crea una nuova collezione all'interno di un database esistente.
    """
    verify_user_database(db_name, current_user)

    try:
        response = requests.post(f"{MONGO_SERVICE_URL}/{db_name}/create_collection/",
                                 params={"collection_name": collection_name})
        if response.status_code != 200:
            print(response.__dict__)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Errore nella creazione della collezione.")
        return {"message": f"Collection '{collection_name}' created successfully in database '{db_name}'."}
    except Exception as e:

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore nella creazione della collezione: {str(e)}")


@router.get("/{db_name}/list_collections/", summary="Elenca le collezioni in un database",
            response_description="Elenco delle collezioni presenti nel database")
async def list_collections(db_name: str, current_user: UserInDB = Depends(get_current_user)):
    """
    Recupera l'elenco di tutte le collezioni in un database specifico.
    """
    verify_user_database(db_name, current_user)

    try:
        response = requests.get(f"{MONGO_SERVICE_URL}/{db_name}/list_collections/")
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Errore nel recupero delle collezioni.")
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore nel recupero delle collezioni: {str(e)}")


@router.delete("/{db_name}/delete_collection/{collection_name}/", summary="Elimina una collezione esistente",
               response_description="La collezione è stata eliminata con successo")
async def delete_collection(db_name: str, collection_name: str, current_user: UserInDB = Depends(get_current_user)):
    """
    Elimina una collezione esistente in un database specifico.
    """
    verify_user_database(db_name, current_user)

    try:
        response = requests.delete(f"{MONGO_SERVICE_URL}/{db_name}/delete_collection/{collection_name}/")
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Errore nell'eliminazione della collezione.")
        return {"message": f"Collection '{collection_name}' deleted successfully from database '{db_name}'."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore nell'eliminazione della collezione: {str(e)}")


# Funzione per caricare e associare schemi YAML alle collezioni
@router.post("/{db_name}/{collection_name}/upload_schema/", summary="Carica uno o più schemi YAML per una collezione specifica")
async def upload_schema(db_name: str, collection_name: str, files: List[UploadFile] = File(...), current_user: UserInDB = Depends(get_current_user)):
    """
    Carica uno o più schemi YAML per una collezione specifica in un database.

    **Parametri:**
    - **db_name**: Nome del database
    - **collection_name**: Nome della collezione
    - **files**: Lista di file YAML contenenti gli schemi
    """
    verify_user_database(db_name, current_user)

    try:
        files_data = []
        for file in files:
            content = await file.read()
            files_data.append({
                "filename": file.filename,
                "content": content.decode("utf-8")
            })

        response = requests.post(
            f"{MONGO_SERVICE_URL}/upload_schema/{db_name}/{collection_name}/",
            json={"files": files_data}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Errore durante il caricamento degli schemi.")

        return {"message": f"Schemi per la collezione '{collection_name}' nel database '{db_name}' caricati con successo."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore durante il caricamento degli schemi: {str(e)}")


# Endpoint per aggiungere un documento in una collezione convalidato tramite schema
@router.post("/{db_name}/{collection_name}/add_item/", summary="Aggiungi un documento in una collezione convalidato tramite schema")
async def add_item(db_name: str, collection_name: str, data: Dict[str, Any], current_user: UserInDB = Depends(get_current_user)):
    """
    Aggiungi un nuovo documento in una collezione esistente, convalidato tramite uno schema YAML specifico.

    **Parametri:**
    - **db_name**: Nome del database
    - **collection_name**: Nome della collezione
    - **data**: Dati del documento da inserire
    """
    verify_user_database(db_name, current_user)

    try:
        response = requests.post(
            f"{MONGO_SERVICE_URL}/{db_name}/{collection_name}/add_item/",
            json=data
        )
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Errore nell'aggiunta del documento.")
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore nell'aggiunta del documento: {str(e)}")


@router.post("/{db_name}/get_items/{collection_name}/", summary="Recupera tutti i documenti di una collezione",
             response_description="Elenco dei documenti nella collezione")
async def get_items(db_name: str, collection_name: str, filter: Optional[Dict[str, Any]] = None,
                    current_user: UserInDB = Depends(get_current_user)):
    """
    Recupera tutti i documenti di una collezione specifica, con la possibilità di applicare un filtro.
    """
    verify_user_database(db_name, current_user)
    query = filter if filter else {}

    try:
        response = requests.post(f"{MONGO_SERVICE_URL}/{db_name}/get_items/{collection_name}/", json=query)
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Errore nel recupero dei documenti.")

        return response.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore nel recupero dei documenti: {str(e)}")


@router.put("/{db_name}/update_item/{collection_name}/{item_id}/", summary="Aggiorna un documento in una collezione",
            response_description="Il documento è stato aggiornato con successo")
async def update_item(db_name: str, collection_name: str, item_id: str, item: Dict[str, Any],
                      current_user: UserInDB = Depends(get_current_user)):
    """
    Aggiorna un documento esistente in una collezione.
    """
    verify_user_database(db_name, current_user)

    try:
        response = requests.put(f"{MONGO_SERVICE_URL}/{db_name}/update_item/{collection_name}/{item_id}/", json=item)
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Errore nell'aggiornamento del documento.")
        return {"message": "Item updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore nell'aggiornamento del documento: {str(e)}")


@router.delete("/{db_name}/delete_item/{collection_name}/{item_id}/", summary="Elimina un documento in una collezione",
               response_description="Il documento è stato eliminato con successo")
async def delete_item(db_name: str, collection_name: str, item_id: str,
                      current_user: UserInDB = Depends(get_current_user)):
    """
    Elimina un documento esistente in una collezione.
    """
    verify_user_database(db_name, current_user)

    try:
        response = requests.delete(f"{MONGO_SERVICE_URL}/{db_name}/delete_item/{collection_name}/{item_id}/")
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Errore nell'eliminazione del documento.")
        return {"message": "Item deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore nell'eliminazione del documento: {str(e)}")


@router.get("/{db_name}/get_item/{collection_name}/{item_id}/", summary="Recupera un documento specifico",
            response_description="Il documento è stato recuperato con successo")
async def get_item(db_name: str, collection_name: str, item_id: str,
                   current_user: UserInDB = Depends(get_current_user)):
    """
    Recupera un documento specifico in una collezione.
    """
    verify_user_database(db_name, current_user)

    try:
        response = requests.get(f"{MONGO_SERVICE_URL}/{db_name}/get_item/{collection_name}/{item_id}/")
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Errore nel recupero del documento.")
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Errore nel recupero del documento: {str(e)}")


@router.delete("/delete_database/{db_name}/", summary="Elimina un database esistente",
               response_description="Il database è stato eliminato con successo")
async def delete_database(db_name: str, current_user: UserInDB = Depends(get_current_user)):
    """
    Elimina un database esistente e rimuovilo dalla lista `databases` dell'utente.

    **Parametri:**
    - **db_name**: Nome del database da eliminare
    """
    verify_user_database(db_name, current_user)

    try:
        # Effettua la richiesta per eliminare il database tramite l'API MongoDB
        response = requests.delete(f"{MONGO_SERVICE_URL}/delete_database/{db_name}/")
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Errore durante l'eliminazione del database")

        # Rimuovi il database dalla lista `databases` dell'utente basandoti solo su `db_name`
        updated_databases = [db for db in current_user.databases if db["db_name"] != db_name]

        # Aggiorna la lista `databases` dell'utente nel database principale
        update_response = requests.put(
            f"{MONGO_SERVICE_URL}/database/update_item/users_collection/{current_user.id}/",
            json={"databases": updated_databases}
        )

        if update_response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Errore durante l'aggiornamento delle informazioni dell'utente")

        return {
            "message": f"Database '{db_name}' eliminato con successo e rimosso dalla lista dei database dell'utente."}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Errore durante l'eliminazione del database: {str(e)}")
