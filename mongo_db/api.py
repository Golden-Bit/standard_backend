from bson import ObjectId
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient

from mongo_db.utils import add_database, get_mongo_client, get_db_instance

app = FastAPI()

# Dizionario globale per mantenere le connessioni ai database
databases = {}


class DBCredentials(BaseModel):
    db_name: str
    username: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = "localhost"
    port: Optional[int] = 27017


# Endpoint per creare un nuovo database
@app.post("/create_database/")
async def create_database(credentials: DBCredentials):
    try:
        db = await add_database(credentials.db_name, credentials.username, credentials.password, credentials.host, credentials.port)
        return {"message": f"Database '{credentials.db_name}' created and connected successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint per ottenere l'elenco dei database esistenti
@app.get("/list_databases/")
async def list_databases():
    client = await get_mongo_client()
    db_list = await client.list_database_names()
    return {"databases": db_list}


# Endpoint per eliminare un database esistente
@app.delete("/delete_database/{db_name}/")
async def delete_database(db_name: str):
    try:
        client = await get_mongo_client()
        await client.drop_database(db_name)
        databases.pop(db_name, None)  # Rimuovi il database dal dizionario se esiste
        return {"message": f"Database '{db_name}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint per creare una nuova collezione in un database specifico
@app.post("/{db_name}/create_collection/")
async def create_collection(db_name: str, collection_name: str):
    try:
        db = get_db_instance(db_name)
        await db.create_collection(collection_name)
        return {"message": f"Collection '{collection_name}' created successfully in database '{db_name}'."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint per ottenere l'elenco delle collezioni in un database specifico
@app.get("/{db_name}/list_collections/")
async def list_collections(db_name: str):
    try:
        db = get_db_instance(db_name)
        collection_list = await db.list_collection_names()
        return {"collections": collection_list}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint per eliminare una collezione in un database specifico
@app.delete("/{db_name}/delete_collection/{collection_name}/")
async def delete_collection(db_name: str, collection_name: str):
    try:
        db = get_db_instance(db_name)
        await db.drop_collection(collection_name)
        return {"message": f"Collection '{collection_name}' deleted successfully from database '{db_name}'."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint per aggiungere un documento in una collezione in un database specifico
class Item(BaseModel):
    name: str
    description: Optional[str] = None


@app.post("/{db_name}/add_item/{collection_name}/")
async def add_item(db_name: str, collection_name: str, item: Item):
    try:
        db = get_db_instance(db_name)
        collection = db[collection_name]
        result = await collection.insert_one(item.dict())
        return {"message": "Item added successfully.", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint per ottenere tutti i documenti di una collezione in un database specifico
@app.get("/{db_name}/get_items/{collection_name}/", response_model=List[Item])
async def get_items(db_name: str, collection_name: str):
    try:
        db = get_db_instance(db_name)
        collection = db[collection_name]
        items = []
        async for item in collection.find():
            item["_id"] = str(item["_id"])
            items.append(item)
        return items
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint per aggiornare un documento in una collezione in un database specifico
@app.put("/{db_name}/update_item/{collection_name}/{item_id}/")
async def update_item(db_name: str, collection_name: str, item_id: str, item: Item):
    try:
        db = get_db_instance(db_name)
        collection = db[collection_name]
        result = await collection.update_one({"_id": ObjectId(item_id)}, {"$set": item.dict()})
        if result.modified_count:
            return {"message": "Item updated successfully."}
        else:
            return {"message": "No item was updated."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint per eliminare un documento in una collezione in un database specifico
@app.delete("/{db_name}/delete_item/{collection_name}/{item_id}/")
async def delete_item(db_name: str, collection_name: str, item_id: str):
    try:
        db = get_db_instance(db_name)
        collection = db[collection_name]
        result = await collection.delete_one({"_id": ObjectId(item_id)})
        if result.deleted_count:
            return {"message": "Item deleted successfully."}
        else:
            return {"message": "No item was deleted."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoint per recuperare un documento specifico in un database specifico
@app.get("/{db_name}/get_item/{collection_name}/{item_id}/", response_model=Item)
async def get_item(db_name: str, collection_name: str, item_id: str):
    try:
        db = get_db_instance(db_name)
        collection = db[collection_name]
        item = await collection.find_one({"_id": ObjectId(item_id)})
        if item:
            item["_id"] = str(item["_id"])
            return item
        else:
            raise HTTPException(status_code=404, detail="Item not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Codice per eseguire l'applicazione
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
