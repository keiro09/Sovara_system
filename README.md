Sovara

A Social Memory-Sharing Platform — Proof of Concept

About the Project

Sovara is a Proof of Concept (PoC) for a social platform where users can create, store, search, and manage memories. The project explores backend development, database integration, and containerization.

Technologies Used

- Python — main programming language
- FastAPI — backend API framework
- MongoDB — stores memory documents
- PostgreSQL — structured data storage in the development setup
- Redis — caching in the development setup
- Docker Compose — manages application services

Note: Technologies listed beyond the currently implemented features should be marked as planned or in development.

Current Features

- Create and store memories
- Retrieve saved memories
- Search memories
- Delete memories
- Explore API endpoints using FastAPI Swagger UI

Getting Started

Prerequisites

- Python
- Docker Desktop
- Git

Run with Docker Compose

1. Clone this repository:

   `git clone https://github.com/keiro09/Sovara_system.git`

2. Open the project folder:

   `cd Sovara_system`

3. Configure the required environment variables locally. Do not commit your `.env` file or credentials.

4. Start the services:

   `docker compose up --build`

5. Open the API documentation:

   `http://localhost:8000/docs`

Some services may require additional configuration depending on the current project setup.

Project Status

Sovara is a learning and development project. Features and database integrations may change as development continues.

Author

Developed as an academic Proof of Concept project.
