import pytest
import httpx
import asyncio
import time

BASE_URL = "http://127.0.0.1:8094"


@pytest.mark.asyncio
async def test_parallel_operations():
    async with httpx.AsyncClient() as client:
        db_name = "timing_test_db_1"

        # Numero di collezioni e richieste parallele
        num_collections = 10

        # 1. Creazione delle collezioni in parallelo
        async def create_collection(index):
            collection_name = f"test_collection_{index}_{time.time()}"
            start_time = time.perf_counter()
            response = await client.post(f"{BASE_URL}/{db_name}/create_collection/",
                                         params={"collection_name": collection_name})
            end_time = time.perf_counter()
            assert response.status_code == 200
            return end_time - start_time

        start_create_time = time.perf_counter()
        create_tasks = [create_collection(i) for i in range(num_collections)]
        create_times = await asyncio.gather(*create_tasks)
        end_create_time = time.perf_counter()
        total_create_time = end_create_time - start_create_time

        print(f"Creation times: {create_times}")
        print(f"Total time for parallel creation: {total_create_time:.4f} seconds")

        # 2. Inserimento dei documenti in parallelo
        async def insert_item(index):
            collection_name = f"test_collection_{index}"
            item = {"name": f"Item {index}", "description": f"Description for item {index}"}
            start_time = time.perf_counter()
            response = await client.post(f"{BASE_URL}/{db_name}/add_item/{collection_name}/", json=item)
            end_time = time.perf_counter()
            assert response.status_code == 200
            return end_time - start_time

        start_insert_time = time.perf_counter()
        insert_tasks = [insert_item(i) for i in range(num_collections)]
        insert_times = await asyncio.gather(*insert_tasks)
        end_insert_time = time.perf_counter()
        total_insert_time = end_insert_time - start_insert_time

        print(f"Insertion times: {insert_times}")
        print(f"Total time for parallel insertion: {total_insert_time:.4f} seconds")

        # 3. Eliminazione delle collezioni in parallelo
        async def delete_collection(index):
            collection_name = f"test_collection_{index}"
            start_time = time.perf_counter()
            response = await client.delete(f"{BASE_URL}/{db_name}/delete_collection/{collection_name}/")
            end_time = time.perf_counter()
            assert response.status_code == 200
            return end_time - start_time

        start_delete_time = time.perf_counter()
        delete_tasks = [delete_collection(i) for i in range(num_collections)]
        delete_times = await asyncio.gather(*delete_tasks)
        end_delete_time = time.perf_counter()
        total_delete_time = end_delete_time - start_delete_time

        print(f"Deletion times: {delete_times}")
        print(f"Total time for parallel deletion: {total_delete_time:.4f} seconds")

        # Elimina il database di test
        await client.delete(f"{BASE_URL}/delete_database/{db_name}/")

        # Asserzioni per verificare che le operazioni parallele siano più veloci
        assert total_create_time < sum(create_times), "Parallel creation should be faster than sequential creation."
        assert total_insert_time < sum(insert_times), "Parallel insertion should be faster than sequential insertion."
        assert total_delete_time < sum(delete_times), "Parallel deletion should be faster than sequential deletion."


if __name__ == "__main__":
    pytest.main()
