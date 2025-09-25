# Cadastral Service API

Этот проект представляет собой FastAPI приложение, которое служит API для получения информации о кадастровых номерах. Он включает в себя следующие возможности:
- Запросы информации о кадастровых номерах.
- Ведение истории запросов.
- Эмуляция внешнего API для получения данных кадастра.
- Регистрация и аутентификация пользователей.
- Миграции базы данных с помощью Alembic.

## Стек технологий

- **Backend Framework:** FastAPI
- **Асинхронная поддержка:** Python 3.10+, Asyncio, Asyncpg
- **База данных:** PostgreSQL
- **ORM/Toolkit для работы с БД:** SQLAlchemy (с асинхронной поддержкой)
- **Миграции базы данных:** Alembic
- **Контейнеризация:** Docker, Docker Compose
- **Тестирование:** Pytest
- **Аутентификация:** JWT, Passlib (для хеширования паролей)
- **HTTP клиент:** httpx (для вызовов внешних API)
## Структура проекта

`your_project/`
- `app/`
  - `__init__.py`
  - `db.py`
  - `main.py`
  - `models.py`
  - `auth.py`
  - `auth_routes.py`
  - `dependencies.py`
- `alembic/`
  - `__init__.py`
  - `versions/`
- `mock_external_server/`
  - `__init__.py`
  - `main.py`
- `tests/`
  - `__init__.py`
  - `test_main.py`
- `docker-compose.test.yml`
- `docker-compose.yml`
- `Dockerfile`
- `requirements.txt`
- `alembic.ini`
- `README.md`
- `.env`


## Предварительные требования

- Установленные Docker и Docker Compose.

## Настройка и установка

1.  **Клонируйте репозиторий:**
    ```bash
    git clone <ваш_url_репозитория>
    cd <ваш_каталог_проекта>
    ```

2.  **Создайте файл `.env`:**
    Скопируйте `.env.example` или создайте `.env` файл. Установите надежный `JWT_SECRET_KEY` для production.
    ```bash
    # Пример содержимого .env (замените значения):
    # DATABASE_URL=postgresql+asyncpg://user:password@localhost:5433/cadastral_db
    # JWT_SECRET_KEY=your-super-secret-key-change-me-in-production
    # EXTERNAL_API_URL=http://your-actual-external-api.com
    ```

3.  **Создайте `Dockerfile` для mock-сервера:**
    *   В папке `mock_external_server/` создайте файл `Dockerfile`:
        ```dockerfile
        # mock_external_server/Dockerfile
        FROM python:3.10-slim

        WORKDIR /app

        COPY requirements.txt .
        RUN pip install --no-cache-dir -r requirements.txt

        COPY . .

        EXPOSE 8001

        CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
        ```
    *   Создайте файл `mock_external_server/requirements.txt`:
        ```txt
        fastapi
        uvicorn[standard]
        pydantic
        ```

4.  **Запуск сервисов для тестирования:**
    ```bash
    docker-compose -f docker-compose.test.yml up --build -d
    ```

## Инициализация миграций базы данных (Alembic)

Alembic используется для управления изменениями схемы БД.

1.  **Инициализация Alembic (один раз):**
    *   Убедитесь, что `docker-compose.yml` (для production/development) запущен.
    *   Выполните в корне проекта:
        ```bash
        docker-compose run --rm app alembic init alembic
        ```
    *   **Настройте `alembic.ini` и `alembic/env.py`**: Убедитесь, что `sqlalchemy.url` и `DATABASE_URL` корректно указывают на вашу БД (например, `cadastral_db_test` для тестов) и используются переменные окружения.

2.  **Создание новой миграции:**
    *   После изменений в `app/models.py`:
        ```bash
        docker-compose run --rm app alembic revision -m "Описание изменений"
        ```

3.  **Применение миграций:**
    *   Применяет все ожидающие миграции:
        ```bash
        docker-compose run --rm app alembic upgrade head
        ```

## Запуск тестов

Для запуска всех тестов:

1.  **Убедитесь, что тестовые сервисы запущены:**
    ```bash
    docker-compose -f docker-compose.test.yml up -d
    ```

2.  **Запустите Pytest:**
    ```bash
    docker-compose -f docker-compose.test.yml run --rm app pytest -v tests/test_main.py
    ```

## Проверка работы сервисов

Проверяйте работу сервисов, просматривая логи и отправляя HTTP-запросы.

1.  **Просмотр логов:**
    *   Все логи:
        ```bash
        docker-compose -f docker-compose.test.yml logs -f
        ```
    *   Логи конкретного сервиса (например, `app`):
        ```bash
        docker-compose -f docker-compose.test.yml logs -f app
        ```

2.  **Проверка Mock External Server:**
    *   С хост-машины (порт 8001):
        ```bash
        curl -X POST "http://localhost:8001/mock_query/" \
        -H "Content-Type: application/json" \
        -d '{"cadastral_number": "123456789012", "latitude": 55.7558, "longitude": 37.6173}'
        ```
        Ожидаемый вывод:
        ```json
        {"cadastral_number":"123456789012","address":"Some Street, 123","value":1500000.5,"status":"Success"}
        ```
    *   Изнутри контейнера `app`:
        ```bash
        docker-compose -f docker-compose.test.yml exec app bash
        curl -X POST "http://external_api_mock:8001/mock_query/" \
        -H "Content-Type: application/json" \
        -d '{"cadastral_number": "123456789012", "latitude": 55.7558, "longitude": 37.6173}'
        exit
        ```

3.  **Проверка Основных API Эндпоинтов (порт 8000):**
    *   **Ping:**
        ```bash
        curl http://localhost:8000/ping
        ```
        Ожидаемый вывод: `{"message":"pong"}`

    *   **Регистрация пользователя:**
        ```bash
        curl -X POST http://localhost:8000/register \
        -H "Content-Type: application/json" \
        -d '{"email": "testuser@example.com", "password": "testpassword123"}'
        ```
        Ожидаемый вывод: `{"message":"User registered successfully. Please log in."}`

    *   **Логин пользователя:**
        ```bash
        curl -X POST http://localhost:8000/login \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=testuser@example.com&password=testpassword123"
        ```
        Скопируйте `access_token` из полученного JSON.

    *   **Получение данных текущего пользователя (требуется токен):**
        Замените `YOUR_ACCESS_TOKEN`.
        ```bash
        curl -X GET http://localhost:8000/users/me \
        -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
        ```

    *   **Отправка запроса (требуется токен):**
        ```bash
        curl -X POST http://localhost:8000/query \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
        -d '{
            "cadastral_number": "123456789012",
            "latitude": 55.7558,
            "longitude": 37.6173
        }'
        ```

    *   **Получение истории (требуется токен):**
        ```bash
        curl -X GET "http://localhost:8000/history" \
        -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
        ```

    *   **Получение истории для конкретного номера (требуется токен):**
        ```bash
        curl -X GET "http://localhost:8000/history?cadastral_number=123456789012" \
        -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
        ```

## Устранение неполадок

-   **`database "user" does not exist`**:
    Убедитесь, что `POSTGRES_DB` и `DATABASE_URL` правильно указывают на `cadastral_db_test` в `docker-compose.test.yml` и `test_main.py`. Выполните полную очистку и пересборку:
    ```bash
    docker-compose -f docker-compose.test.yml down -v
    docker builder prune -a
    docker-compose -f docker-compose.test.yml up --build
    ```

-   **`relation "query_logs" does not exist`**:
    Проверьте `app/models.py` на корректность определения моделей и импортов. Убедитесь, что `Base.metadata.create_all` вызывается корректно (через тесты или Alembic).

-   **`AttributeError: 'coroutine' object has no attribute '...'`**:
    Убедитесь, что все асинхронные операции SQLAlchemy (например, `db.execute`, `db.add`, `db.commit`, `db.refresh`, `conn.run_sync`) имеют `await`.

-   **Ошибки OOM Killer (код выхода 137)**:
    Увеличьте лимиты памяти для Docker Desktop или для сервиса `db` в `docker-compose.yml`.

-   **Внутренние ошибки сервера (5xx)**:
    Проверьте логи контейнера `app-1` для получения подробных сообщений об ошибках.

---

## Остановка сервисов

Когда вы закончите, остановите все запущенные Docker-контейнеры:

*   Для тестового окружения:
    ```bash
    docker-compose -f docker-compose.test.yml down
    ```
*   Для production/development:
    ```bash
    docker-compose down
    ```

Для удаления томов (данных PostgreSQL):

*   Тестовое окружение:
    ```bash
    docker-compose -f docker-compose.test.yml down -v
    ```
*   Production/development:
    ```bash
    docker-compose down -v
    ```