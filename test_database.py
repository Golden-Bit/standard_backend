import pytest
import httpx
import asyncio

BASE_URL = "http://127.0.0.1:8000"

@pytest.mark.asyncio
async def test_parallel_requests():
    async with httpx.AsyncClient() as client:
        # 1. Crea un nuovo database
        db_name = "test_db"
        create_db_response = await client.post(f"{BASE_URL}/create_database/", json={"db_name": db_name})
        assert create_db_response.status_code == 200

        # 2. Crea una collezione
        create_col_response = await client.post(f"{BASE_URL}/{db_name}/create_collection/", params={"collection_name": "test_collection"})
        assert create_col_response.status_code == 200

        # 3. Funzione per inserire un documento
        async def insert_item(index):
            item = {"name": f"Item {index}", "description": f"Description for item {index}"}
            response = await client.post(f"{BASE_URL}/{db_name}/add_item/test_collection/", json=item)
            assert response.status_code == 200
            return response.json()["id"]

        # 4. Inserire più elementi in parallelo
        tasks = [insert_item(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        assert len(results) == 10

        # 5. Verificare che gli elementi siano stati inseriti
        get_items_response = await client.get(f"{BASE_URL}/{db_name}/get_items/test_collection/")
        assert get_items_response.status_code == 200
        items = get_items_response.json()
        assert len(items) == 10

        # 6. Elimina il database di test
        delete_db_response = await client.delete(f"{BASE_URL}/delete_database/{db_name}/")
        assert delete_db_response.status_code == 200

if __name__ == "__main__":
    pytest.main()
