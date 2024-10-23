# MongoDB FastAPI Backend - Detailed Documentation

## Overview

This project is a backend API developed using FastAPI, designed to manage MongoDB databases, collections, and documents. It provides a RESTful interface for interacting with MongoDB, enabling the management of user authentication and authorization alongside database operations. The core functionalities include creating databases and collections, performing CRUD (Create, Read, Update, Delete) operations on documents, and managing user accounts securely with JWT-based authentication.

## Key Features

### 1. **User Management**
   - **Registration**: Allows new users to register by providing a username, email, and password. The password is securely hashed before storage.
   - **Login**: Users can authenticate with their credentials (username and password) to receive a JWT token, which is used for subsequent authenticated requests.
   - **User Profile**: Authenticated users can retrieve and update their profile information.

### 2. **Database and Collection Management**
   - **Create Database**: Create new databases within MongoDB.
   - **List Databases**: Retrieve a list of all databases.
   - **Delete Database**: Delete specified databases.
   - **Create Collection**: Create new collections within a database.
   - **List Collections**: Retrieve a list of all collections in a specific database.
   - **Delete Collection**: Delete specified collections.

### 3. **Document Management**
   - **Insert Document**: Add new documents to a specified collection with optional validation against a schema.
   - **Retrieve Documents**: Retrieve documents from a collection, with support for applying filters.
   - **Update Document**: Update existing documents in a collection by providing the document ID.
   - **Delete Document**: Remove specific documents from a collection.

### 4. **Schema Validation**
   - **Upload Schemas**: Upload YAML schemas that can be used to validate documents before they are inserted into collections.

## API Endpoints

### User Management Endpoints

- **POST `/register/`**
  - **Summary**: Register a new user.
  - **Request Body**: `UserInDB` model (includes username, email, and password).
  - **Response**: Success message upon successful registration.
  
- **POST `/login/`**
  - **Summary**: Authenticate a user.
  - **Request Body**: OAuth2PasswordRequestForm (username and password).
  - **Response**: JWT token for authenticated access.
  
- **GET `/users_collection/me/`**
  - **Summary**: Retrieve the profile of the authenticated user.
  - **Response**: User profile information.

- **PUT `/users_collection/me/`**
  - **Summary**: Update the authenticated user's profile.
  - **Request Body**: `User` model (with optional updates).
  - **Response**: Success message upon successful update.

### Database Management Endpoints

- **POST `/create_database/`**
  - **Summary**: Create a new MongoDB database.
  - **Request Body**: `DBCredentials` model.
  - **Response**: Success message upon successful database creation.
  
- **GET `/list_databases/`**
  - **Summary**: Retrieve a list of all databases.
  - **Response**: List of database names.
  
- **DELETE `/delete_database/{db_name}/`**
  - **Summary**: Delete a specified database.
  - **Response**: Success message upon successful deletion.

### Collection Management Endpoints

- **POST `/{db_name}/create_collection/`**
  - **Summary**: Create a new collection within a specified database.
  - **Request Body**: Collection name.
  - **Response**: Success message upon successful collection creation.
  
- **GET `/{db_name}/list_collections/`**
  - **Summary**: Retrieve a list of all collections within a specified database.
  - **Response**: List of collection names.
  
- **DELETE `/{db_name}/delete_collection/{collection_name}/`**
  - **Summary**: Delete a specified collection.
  - **Response**: Success message upon successful deletion.

### Document Management Endpoints

- **POST `/{db_name}/{collection_name}/add_item/`**
  - **Summary**: Add a new document to a specified collection.
  - **Request Body**: Document data (validated against an optional schema).
  - **Response**: Success message and the ID of the inserted document.
  
- **POST `/{db_name}/get_items/{collection_name}/`**
  - **Summary**: Retrieve documents from a specified collection.
  - **Request Body**: Optional filter dictionary for querying specific documents.
  - **Response**: List of documents matching the filter.
  
- **PUT `/{db_name}/update_item/{collection_name}/{item_id}/`**
  - **Summary**: Update a specified document within a collection.
  - **Request Body**: Updated document data.
  - **Response**: Success message upon successful update.
  
- **DELETE `/{db_name}/delete_item/{collection_name}/{item_id}/`**
  - **Summary**: Delete a specified document.
  - **Response**: Success message upon successful deletion.

### Schema Management Endpoint

- **POST `/upload_schema/{db_name}/{collection_name}/`**
  - **Summary**: Upload YAML schemas for a specific collection.
  - **Request Body**: List of YAML schema files.
  - **Response**: Success message upon successful schema upload.

## Project Implementation

### User Authentication and Authorization

The project implements secure user authentication using JWT tokens. Users register with a username and password, which are securely hashed before being stored in the database. Upon successful login, users receive a JWT token that is used for subsequent requests requiring authentication.

### Handling Database and Collection Operations

The API provides endpoints to create, list, and delete databases and collections. It uses MongoDB as the backend database, and all operations are performed using the MongoDB Python driver.

### Document CRUD Operations

Documents within collections can be managed via CRUD operations. The `get_items` endpoint supports optional filtering to retrieve specific documents based on user-defined criteria.

### Schema Validation

Schemas can be uploaded to validate documents before they are inserted into collections. This ensures data integrity and consistency within the database.

## Handling Filtering in Document Retrieval

In the current implementation, filtering is applied by passing a filter dictionary to the `get_items` endpoint. This filter is used to match documents within a MongoDB collection. However, an important aspect to note is that the filter is applied directly within the MongoDB query, which may have specific syntax requirements.

**Example Filter Usage:**
```json
{
  "username": "desired_username"
}
```

This filter will retrieve documents where the `username` field matches `"desired_username"`.

## Conclusion

This FastAPI backend provides a comprehensive and secure interface for managing MongoDB databases and user authentication. With its robust set of features, it is well-suited for applications requiring dynamic data management and secure user access.