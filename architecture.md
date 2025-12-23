# Архитектура проекта Bitrix24 Lead Transfer

## Общее описание

Веб-приложение для трансфера лидов в Bitrix24, состоящее из двух основных частей:
- **Backend**: FastAPI сервис с REST API
- **Frontend**: React приложение с TypeScript

Каждый workflow использует отдельную SQLite базу данных для изоляции данных.

## Структура проекта

```
b24-transfer-lead/
├── src/
│   ├── backend/                    # Backend приложение
│   │   ├── main.py                # Точка входа FastAPI приложения
│   │   ├── api/                   # API endpoints
│   │   │   └── v1/
│   │   │       ├── auth.py         # Авторизация (login/logout)
│   │   │       ├── users.py        # Управление пользователями (admin)
│   │   │       ├── workflows.py   # CRUD workflow
│   │   │       ├── leads.py        # CRUD лидов
│   │   │       ├── webhook.py      # Webhook от Bitrix24
│   │   │       ├── public.py       # Публичный API для создания лидов
│   │   │       └── dependencies.py # Зависимости для авторизации
│   │   ├── models/                # Модели данных SQLAlchemy
│   │   │   ├── user.py            # Модель пользователя
│   │   │   ├── workflow.py        # Модель workflow
│   │   │   ├── workflow_field_mapping.py # Модель маппинга полей workflow
│   │   │   ├── lead.py            # Модель лида
│   │   │   └── lead_field.py     # Модель дополнительных полей лида
│   │   ├── services/              # Бизнес-логика
│   │   │   ├── database.py        # Управление БД workflow
│   │   │   ├── bitrix24.py        # Интеграция с Bitrix24 API
│   │   │   └── auth.py            # Логика авторизации
│   │   ├── core/                  # Основные настройки
│   │   │   ├── config.py          # Конфигурация приложения
│   │   │   └── database.py        # Подключение к основной БД
│   │   └── utils/                 # Утилиты
│   │       ├── csv_parser.py      # Парсинг CSV файлов
│   │       └── cache.py            # Кэширование данных с TTL
│   └── frontend/                   # Frontend приложение
│       ├── src/
│       │   ├── components/        # Переиспользуемые компоненты
│       │   │   ├── Layout.tsx     # Основной layout с навигацией
│       │   │   ├── ProtectedRoute.tsx # Защищенный роут
│       │   │   ├── LeadsTable.tsx  # Таблица лидов
│       │   │   ├── LeadForm.tsx    # Форма добавления лида
│       │   │   └── CSVUpload.tsx   # Компонент загрузки CSV
│       │   ├── pages/              # Страницы приложения
│       │   │   ├── LoginPage.tsx  # Страница авторизации
│       │   │   ├── WorkflowsPage.tsx # Список workflow
│       │   │   ├── LeadsPage.tsx   # Страница лидов
│       │   │   ├── AdminUsersPage.tsx # Управление пользователями
│       │   │   └── AdminWorkflowsPage.tsx # Все workflow (admin)
│       │   ├── stores/             # Zustand сторы
│       │   │   ├── authStore.ts    # Состояние авторизации
│       │   │   ├── workflowStore.ts # Состояние workflow
│       │   │   └── leadsStore.ts   # Состояние лидов
│       │   ├── services/           # API клиенты
│       │   │   └── api.ts          # Axios клиент с interceptors
│       │   ├── types/              # TypeScript типы
│       │   │   └── index.ts        # Типы для всех сущностей
│       │   ├── App.tsx             # Главный компонент с роутингом
│       │   └── main.tsx            # Точка входа React
│       ├── package.json            # Зависимости frontend
│       ├── vite.config.ts          # Конфигурация Vite
│       ├── tailwind.config.js      # Конфигурация Tailwind CSS
│       └── tsconfig.json           # Конфигурация TypeScript
├── workflows/                      # Директория для БД workflow
├── pyproject.toml                  # Python зависимости
├── Dockerfile.backend              # Dockerfile для backend сервиса
├── Dockerfile.frontend             # Dockerfile для frontend сервиса
├── docker-compose.yml              # Docker Compose конфигурация для запуска приложения
├── nginx.conf                      # Конфигурация Nginx для frontend (production)
└── architecture.md                 # Этот файл
```

## Backend компоненты

### Модели данных

#### User (`src/backend/models/user.py`)
Модель пользователя для основной БД:
- `id`: Integer, primary key
- `username`: String, unique, indexed
- `password_hash`: String (bcrypt hash)
- `role`: String (admin/user)
- `created_at`: DateTime
- `workflows`: Relationship к Workflow (workflows созданные пользователем)
- `accessible_workflows`: Relationship к Workflow через промежуточную таблицу user_workflow_access (workflows к которым у пользователя есть доступ)

#### Workflow (`src/backend/models/workflow.py`)
Модель workflow для основной БД:
- `id`: Integer, primary key
- `name`: String
- `bitrix24_webhook_url`: String (полный URL webhook: https://domain.bitrix24.ru/rest/1/token/)
- `user_id`: Integer, ForeignKey to User
- `created_at`: DateTime
- `entity_type`: String (default: "lead") - тип сущности: "lead" или "deal"
- `deal_category_id`: Integer (nullable) - ID воронки для сделок
- `deal_stage_id`: String (nullable) - ID стадии для сделок
- `lead_status_id`: String (nullable, default: "NEW") - ID статуса для лидов
- `app_token`: String (nullable) - токен приложения для проверки подлинности webhook событий
- `bitrix24_domain`: String (nullable, indexed) - домен портала Bitrix24 для автоматического определения workflow в webhook событиях
- `api_token`: String (nullable, unique, indexed) - уникальный токен для публичного API endpoint'а
- `user`: Relationship к User (создатель workflow)
- `accessible_users`: Relationship к User через промежуточную таблицу user_workflow_access (пользователи с доступом к workflow)
- `field_mappings`: Relationship к WorkflowFieldMapping

#### UserWorkflowAccess (`src/backend/models/user_workflow_access.py`)
Промежуточная таблица для many-to-many связи между User и Workflow:
- `user_id`: Integer, ForeignKey to User, primary key, indexed
- `workflow_id`: Integer, ForeignKey to Workflow, primary key, indexed
- Используется для предоставления доступа пользователям к workflow, которые они не создавали

#### WorkflowFieldMapping (`src/backend/models/workflow_field_mapping.py`)
Модель маппинга полей для основной БД:
- `id`: Integer, primary key
- `workflow_id`: Integer, ForeignKey to Workflow, indexed
- `field_name`: String - имя поля в нашей системе (например, "email", "company")
- `display_name`: String - человекочитаемое название для отображения в UI (например, "Email", "Company")
- `bitrix24_field_id`: String - ID поля в Bitrix24 (например, "EMAIL", "COMPANY_TITLE")
- `bitrix24_field_name`: String - человеческое название поля из Bitrix24 (для отображения)
- `entity_type`: String - тип сущности ("lead" или "deal")
- `update_on_event`: Boolean (default: False) - обновлять это поле при получении webhook событий от Bitrix24
- `created_at`: DateTime
- `workflow`: Relationship к Workflow

#### Lead (`src/backend/models/lead.py`)
Модель лида для БД workflow:
- `id`: Integer, primary key
- `phone`: String, indexed
- `name`: String
- `status`: String (nullable)
- `bitrix24_lead_id`: String (nullable), indexed
- `assigned_by_name`: String (nullable) - имя и фамилия ответственного за лид/сделку из Bitrix24
- `status_semantic_id`: String (nullable) - семантический ID статуса (S - успешный, F - неуспешный) для определения цвета отображения
- `created_at`: DateTime
- `updated_at`: DateTime
- `fields`: Relationship к LeadField (дополнительные поля лида)

#### LeadField (`src/backend/models/lead_field.py`)
Модель дополнительных полей лида для БД workflow:
- `id`: Integer, primary key
- `lead_id`: Integer, ForeignKey to Lead, indexed
- `field_name`: String, indexed - имя поля (соответствует field_name из маппинга)
- `field_value`: String - значение поля
- `created_at`: DateTime
- `lead`: Relationship к Lead

### Сервисы

#### DatabaseService (`src/backend/services/database.py`)
Управление базами данных workflow:
- `get_workflow_db_path(workflow_id)`: Получить путь к БД workflow
- `get_workflow_engine(workflow_id)`: Получить SQLAlchemy engine
- `init_workflow_db(workflow_id)`: Инициализировать БД workflow (создает таблицы для Lead и LeadField)
- `get_workflow_session(workflow_id)`: Получить сессию БД
- `delete_workflow_db(workflow_id)`: Удалить БД workflow

#### Bitrix24Service (`src/backend/services/bitrix24.py`)
Интеграция с Bitrix24 REST API через библиотеку fast-bitrix24:
- `__init__(webhook_url)`: Инициализация с полным webhook URL
- `create_lead(name, phone, status_id, extra_fields)`: Создать лид в Bitrix24 с дополнительными полями
- `get_lead(lead_id)`: Получить данные лида
- `update_lead_status(lead_id, status_id)`: Обновить статус лида
- `get_deal_categories()`: Получить список воронок сделок через `crm.category.list`
- `get_lead_statuses()`: Получить список статусов лидов через `crm.status.list` (использует кэширование на 1 день, ключ кэша - webhook_url)
- `get_deal_stages(category_id)`: Получить список стадий сделок для воронки через `crm.status.list`
- `create_deal(name, phone, category_id, stage_id, extra_fields)`: Создать сделку в Bitrix24 через `crm.deal.add` с дополнительными полями
- `get_lead_fields()`: Получить список полей лида через `crm.lead.fields` (возвращает id, name, type)
- `get_deal_fields()`: Получить список полей сделки через `crm.deal.fields` (возвращает id, name, type)
- Использует `BitrixAsync` из fast-bitrix24 для асинхронных операций

#### AuthService (`src/backend/services/auth.py`)
Авторизация и управление пользователями:
- `hash_password(password)`: Хеширование пароля
- `verify_password(password, hash)`: Проверка пароля
- `create_session(user_id, username, role)`: Создание сессии
- `get_session(session_id)`: Получение данных сессии
- `delete_session(session_id)`: Удаление сессии
- `authenticate_user(db, username, password)`: Аутентификация
- `create_user(db, username, password, role)`: Создание пользователя

### API Endpoints

#### Auth (`/api/v1/auth`)
- `POST /login`: Авторизация пользователя
- `POST /logout`: Выход из системы
- `GET /me`: Получить информацию о текущем пользователе

#### Users (`/api/v1/users`) - Admin only
- `GET /`: Список всех пользователей
- `POST /`: Создание нового пользователя (принимает username, password, role, workflow_ids - список ID workflow для предоставления доступа)

#### Workflows (`/api/v1/workflows`)
- `GET /`: Список workflow текущего пользователя (admin видит все, обычные пользователи видят свои workflow и те, к которым им предоставлен доступ через user_workflow_access)
- `POST /`: Создание workflow (принимает полный webhook URL)
- `GET /{id}`: Получить workflow по ID
- `DELETE /{id}`: Удалить workflow
- `GET /{id}/settings`: Получить настройки workflow (включая bitrix24_webhook_url, app_token, webhook_endpoint_url - полный URL для отправки событий из Bitrix24, api_token и public_api_url - полный URL для публичного API endpoint)
- `PUT /{id}/settings`: Обновить настройки workflow (включая bitrix24_webhook_url и app_token, автоматически обновляет bitrix24_domain при изменении webhook URL)
- `GET /{id}/settings/funnels`: Получить список воронок сделок из Bitrix24
- `GET /{id}/settings/stages`: Получить список стадий для воронки (query param: `category_id`, default: 0)
- `GET /{id}/settings/lead-statuses`: Получить список статусов лидов из Bitrix24
- `GET /{id}/fields`: Получить список доступных полей из Bitrix24 для маппинга (admin only, query param: `entity_type`, default: "lead")
- `POST /{id}/fields/mapping`: Создать маппинг поля (admin only, требует field_name, display_name, bitrix24_field_id, entity_type)
- `GET /{id}/fields/mapping`: Получить список маппингов полей для workflow
- `PUT /{id}/fields/mapping/{mapping_id}`: Обновить маппинг поля (admin only)
- `DELETE /{id}/fields/mapping/{mapping_id}`: Удалить маппинг поля (admin only)
- `POST /{id}/settings/generate-token`: Генерировать/регенерировать API токен для публичного endpoint'а (admin only)
- `GET /{id}/stats/conversion`: Получить статистику конверсии workflow (total, successful, percentage)

#### Leads (`/api/v1/workflows/{workflow_id}/leads`)
- `GET /leads`: Список лидов workflow (включает дополнительные поля в поле `fields`)
- `POST /leads`: Создание лида или сделки (в зависимости от настроек workflow, поддерживает дополнительные поля через маппинг)
- `POST /leads/upload`: Загрузка лидов/сделок из CSV (в зависимости от настроек workflow, поддерживает дополнительные поля через маппинг)
- `GET /leads/export`: Экспорт лидов workflow в CSV файл (возвращает CSV файл с заголовками и данными всех лидов, включая дополнительные поля)
  - Принимает CSV файл и опциональные параметры:
    - `column_mapping` (JSON строка) для маппинга колонок CSV на поля маппинга
    - `limit` (строка с числом) для ограничения количества обрабатываемых строк
  - Формат `column_mapping`: `{"CSV_Column_Name": "field_name", ...}` (например, `{"Email": "email", "Company": "company"}`)
  - Обязательные поля: phone и name должны быть замаплены
  - Если `limit` указан, обрабатываются только первые N строк CSV файла
  - Применяет маппинг полей при создании лида/сделки в Bitrix24
  - Сохраняет дополнительные поля в таблицу `lead_fields`

#### Public API (`/api/v1/public`)
- `POST /workflows/{token}/leads`: Создать лид через публичный API endpoint
- `GET /workflows/{token}/leads`: Создать лид через публичный API endpoint (поддерживается для удобства тестирования)
  - Поддержка JSON body (POST): `{"name": "...", "phone": "...", "email": "...", ...}` (дополнительные поля передаются по именам из маппинга)
  - Поддержка query параметров (GET/POST): `?name=...&phone=...&email=...`
  - Находит workflow по `api_token`
  - Применяет маппинг полей при создании лида/сделки в Bitrix24
  - Сохраняет дополнительные поля в таблицу `lead_fields`
  - Примечание: GET запросы поддерживаются для удобства, но POST рекомендуется для production использования

#### Webhook (`/api/v1/webhook`)
- `POST /`: Обработка событий от Bitrix24 (единый endpoint для всех workflow)
  - Автоматически определяет workflow по домену из события (`auth[domain]`)
  - Проверяет токен приложения из события (`auth[application_token]`) с сохраненным `app_token` в workflow
  - Если токен не настроен в workflow, проверка не выполняется (для обратной совместимости)
  - Обрабатывает события `ONCRMLEADUPDATE`, `ONCRMLEADADD`, `ONCRMDEALUPDATE`, `ONCRMDEALADD`
  - Для событий лидов (`ONCRMLEADUPDATE`, `ONCRMLEADADD`):
    - Извлекает `STATUS_ID` и обновляет статус лида
    - Извлекает `STATUS_SEMANTIC_ID` и сохраняет в `status_semantic_id` (S - успешный, F - неуспешный)
    - Извлекает `ASSIGNED_BY_ID` и получает имя пользователя через `Bitrix24Service.get_user()`, сохраняет в `assigned_by_name`
  - Для событий сделок (`ONCRMDEALUPDATE`, `ONCRMDEALADD`):
    - Извлекает `STAGE_ID` и обновляет статус лида
    - Извлекает `STAGE_SEMANTIC_ID` и сохраняет в `status_semantic_id` (S - успешный, F - неуспешный)
    - Извлекает `ASSIGNED_BY_ID` и получает имя пользователя через `Bitrix24Service.get_user()`, сохраняет в `assigned_by_name`

### Утилиты

#### CSV Parser (`src/backend/utils/csv_parser.py`)
Парсинг CSV файлов для массовой загрузки лидов:
- `get_csv_headers(csv_content)`: Получение заголовков CSV файла (колонок)
- `parse_csv_leads(csv_content, column_mapping)`: Парсинг CSV и извлечение лидов
  - `csv_content`: Содержимое CSV файла
  - `column_mapping`: Опциональный маппинг колонок CSV на имена полей (например, `{"Email": "email", "Company": "company"}`)
  - Если `column_mapping` не указан, используется автоматическое определение phone и name по названиям колонок
  - Возвращает список словарей с данными лидов, включая все колонки из CSV

#### Cache (`src/backend/utils/cache.py`)
Кэширование данных с TTL (Time To Live) для уменьшения количества запросов к внешним API:
- `TTLCache(default_ttl)`: Класс для in-memory кэширования с временем жизни записей
  - `get(key)`: Получить значение из кэша (возвращает None, если ключ не найден или истек срок действия)
  - `set(key, value, ttl)`: Установить значение в кэш с указанным TTL
  - `clear()`: Очистить весь кэш
  - `remove(key)`: Удалить конкретный ключ из кэша
- `lead_statuses_cache`: Глобальный экземпляр кэша для статусов лидов (TTL = 1 день = 86400 секунд)
  - Используется в `Bitrix24Service.get_lead_statuses()` для кэширования статусов лидов по ключу `lead_statuses:{webhook_url}`
  - Кэш привязан к webhook_url, так как разные порталы Bitrix24 могут иметь разные статусы

#### Database Migration (`src/backend/utils/migrate_db.py`)
Миграция схемы базы данных:
- `migrate_workflows_table()`: Обновление таблицы workflows для использования bitrix24_webhook_url
- `migrate_workflow_settings()`: Добавление полей настроек workflow (entity_type, deal_category_id, deal_stage_id, lead_status_id)
- `migrate_workflow_app_token()`: Добавление полей app_token и bitrix24_domain, извлечение домена из существующих webhook URL
- `migrate_workflow_api_token()`: Добавление поля api_token в таблицу workflows с уникальным индексом
- `migrate_workflow_field_mapping()`: Создание таблицы workflow_field_mappings в основной БД, добавление поля display_name для существующих таблиц, добавление поля update_on_event для автоматического обновления полей при webhook событиях
- `migrate_lead_assigned_by_and_semantic()`: Добавление полей `assigned_by_name` и `status_semantic_id` в таблицу leads во всех существующих БД workflow, добавление поля update_on_event для автоматического обновления полей при webhook событиях
- `migrate_user_workflow_access()`: Создание таблицы user_workflow_access для many-to-many связи между пользователями и workflow

#### Bitrix24 URL Parser (`src/backend/utils/bitrix24_url.py`)
Утилиты для работы с Bitrix24 webhook URL:
- `parse_bitrix24_webhook_url(webhook_url)`: Парсинг webhook URL и извлечение portal_url и webhook_token
- `extract_domain_from_webhook_url(webhook_url)`: Извлечение домена портала из webhook URL

## Frontend компоненты

### Страницы

#### LoginPage (`src/frontend/src/pages/LoginPage.tsx`)
Страница авторизации с формой входа.

#### WorkflowsPage (`src/frontend/src/pages/WorkflowsPage.tsx`)
Список workflow пользователя с возможностью создания и удаления:
- Отображение процента конверсии для каждого workflow (загружается через `/api/v1/workflows/{id}/stats/conversion`)
- Процент конверсии отображается рядом с названием workflow в карточке

#### LeadsPage (`src/frontend/src/pages/LeadsPage.tsx`)
Страница управления лидами workflow с таблицей и формами:
- Отображение статистики конверсии
- Кнопка экспорта лидов в CSV (отображается только если есть лиды)
- Кнопка загрузки CSV файла
- Кнопка добавления лида вручную

#### WorkflowSettingsPage (`src/frontend/src/pages/WorkflowSettingsPage.tsx`)
Страница настройки workflow:
- Редактирование webhook URL Bitrix24
- Редактирование токена приложения для проверки webhook событий
- Отображение полного адреса endpoint для событий Bitrix24 (webhook_endpoint_url) с кнопкой копирования
- Выбор типа сущности (лид/сделка)
- Для сделок: выбор воронки и стадии из Bitrix24
- Для лидов: выбор статуса из Bitrix24
- Сохранение настроек workflow
- Для админа: отображение публичного API endpoint для добавления лидов (api_token и public_api_url) с возможностью генерации/регенерации токена

#### AdminUsersPage (`src/frontend/src/pages/AdminUsersPage.tsx`)
Админ-панель для управления пользователями:
- Создание пользователей с указанием доступа к workflow через выбор из списка доступных workflow
- Отображение списка всех пользователей

#### AdminWorkflowsPage (`src/frontend/src/pages/AdminWorkflowsPage.tsx`)
Админ-панель для просмотра всех workflow.

### Компоненты

#### Layout (`src/frontend/src/components/Layout.tsx`)
Основной layout с навигацией и информацией о пользователе.

#### ProtectedRoute (`src/frontend/src/components/ProtectedRoute.tsx`)
Компонент для защиты роутов, требующих авторизации.

#### LeadsTable (`src/frontend/src/components/LeadsTable.tsx`)
Таблица лидов с фильтрацией и сортировкой:
- Отображает колонку "Ответственный" с именем и фамилией ответственного из поля `assigned_by_name`
- Цветовая индикация статусов на основе `status_semantic_id`:
  - Зеленый цвет (`bg-green-100 text-green-800`) для успешных статусов (`status_semantic_id === 'S'`)
  - Красный цвет (`bg-red-100 text-red-800`) для неуспешных статусов (`status_semantic_id === 'F'`)
  - Синий цвет (`bg-blue-100 text-blue-800`) по умолчанию для остальных статусов

#### LeadForm (`src/frontend/src/components/LeadForm.tsx`)
Модальное окно для добавления лида вручную.

#### CSVUpload (`src/frontend/src/components/CSVUpload.tsx`)
Модальное окно для загрузки CSV файла с лидами:
- Загрузка CSV файла
- Автоматическое определение заголовков CSV и подсчет количества строк данных
- Выбор маппинга колонок CSV на поля маппинга workflow (phone, name и дополнительные поля)
- Автоматическое определение phone и name по названиям колонок (phone, телефон, tel, номер для phone; name, имя, fio, фио для name)
- Валидация обязательных полей (phone и name должны быть замаплены) через проверку значений в маппинге
- Выбор количества обрабатываемых строк: все строки или произвольное количество (с ограничением максимума)
- Отображение общего количества строк в CSV файле

### Stores (Zustand)

#### authStore (`src/frontend/src/stores/authStore.ts`)
Управление состоянием авторизации:
- `user`: Текущий пользователь
- `loading`: Состояние загрузки
- `login(username, password)`: Вход
- `logout()`: Выход
- `checkAuth()`: Проверка авторизации

#### workflowStore (`src/frontend/src/stores/workflowStore.ts`)
Управление состоянием workflow:
- `workflows`: Список workflow
- `loading`: Состояние загрузки
- `fetchWorkflows()`: Загрузка списка
- `createWorkflow(data)`: Создание workflow
- `deleteWorkflow(id)`: Удаление workflow

#### leadsStore (`src/frontend/src/stores/leadsStore.ts`)
Управление состоянием лидов:
- `leads`: Список лидов
- `loading`: Состояние загрузки
- `fetchLeads(workflowId)`: Загрузка лидов
- `createLead(workflowId, phone, name, additionalFields)`: Создание лида с дополнительными полями
- `uploadCSV(workflowId, file, columnMapping)`: Загрузка CSV с маппингом колонок (columnMapping - опциональный маппинг колонок CSV на поля маппинга)

### API Client

#### api.ts (`src/frontend/src/services/api.ts`)
Axios клиент с interceptors для авторизации:
- `authAPI`: Методы авторизации
- `usersAPI`: Методы управления пользователями
- `workflowsAPI`: Методы управления workflow и настройками (getSettings, updateSettings, getFunnels, getStages, getLeadStatuses, getConversionStats)
- `leadsAPI`: Методы управления лидами (list, create, uploadCSV с поддержкой маппинга колонок, exportCSV для экспорта в CSV файл)

## Поток данных

### Создание лида/сделки
1. Пользователь добавляет лид (вручную/CSV/API/публичный API)
2. Frontend/клиент отправляет запрос на `/api/v1/workflows/{id}/leads` или `/api/v1/public/workflows/{token}/leads`
3. Backend получает маппинги полей для workflow из таблицы `workflow_field_mappings`
4. Backend сохраняет лид в БД workflow с базовыми полями (name, phone)
5. Backend сохраняет дополнительные поля в таблицу `lead_fields`
6. Backend применяет маппинг: преобразует имена полей из запроса в Bitrix24 field IDs
7. Backend проверяет настройки workflow (`entity_type`)
8. Если `entity_type == "deal"`: создает сделку в Bitrix24 с указанной воронкой, стадией и дополнительными полями
9. Если `entity_type == "lead"`: создает лид в Bitrix24 с указанным статусом и дополнительными полями
10. Сохраняется `bitrix24_lead_id` в БД
11. Frontend обновляет таблицу

### Загрузка лидов/сделок из CSV
1. Пользователь выбирает CSV файл в компоненте CSVUpload
2. Frontend парсит заголовки CSV файла и подсчитывает количество строк данных
3. Frontend загружает маппинги полей для workflow
4. Пользователь выбирает маппинг колонок CSV на поля маппинга (phone, name и дополнительные поля)
5. Пользователь выбирает количество обрабатываемых строк (все или произвольное количество)
6. Frontend валидирует маппинг: проверяет наличие phone и name в значениях маппинга
7. Frontend отправляет CSV файл, маппинг колонок и опциональный limit на `/api/v1/workflows/{id}/leads/upload`
8. Backend парсит CSV с применением маппинга колонок через `parse_csv_leads(csv_content, column_mapping)`
9. Если указан limit, Backend ограничивает количество обрабатываемых строк первыми N строками
10. Для каждой строки CSV:
    - Backend применяет маппинг колонок: преобразует колонки CSV в имена полей маппинга
    - Backend получает маппинги полей для workflow из таблицы `workflow_field_mappings`
    - Backend сохраняет лид в БД workflow с базовыми полями (name, phone)
    - Backend сохраняет дополнительные поля в таблицу `lead_fields`
    - Backend применяет маппинг: преобразует имена полей в Bitrix24 field IDs
    - Backend создает лид/сделку в Bitrix24 в зависимости от настроек workflow
11. Frontend обновляет таблицу с созданными лидами

### Webhook от Bitrix24
1. Bitrix24 отправляет событие на единый endpoint `/api/v1/webhook` (form-data format)
2. Backend извлекает домен портала из события (`auth[domain]`)
3. Backend находит workflow по `bitrix24_domain` в базе данных
4. Backend проверяет токен приложения из события (`auth[application_token]`) с сохраненным `app_token` в workflow (если токен настроен)
5. Если токены совпадают (или токен не настроен), Backend определяет тип события:
   - Для событий лидов (`ONCRMLEADUPDATE`, `ONCRMLEADADD`): извлекает `STATUS_ID` из поля `FIELDS.STATUS_ID` или `STATUS_ID`
   - Для событий сделок (`ONCRMDEALUPDATE`, `ONCRMDEALADD`): извлекает `STAGE_ID` из поля `FIELDS.STAGE_ID` или `STAGE_ID`
6. Backend обновляет статус лида в БД workflow используя соответствующий ID (STATUS_ID для лидов, STAGE_ID для сделок)
7. Frontend получает обновления при следующей загрузке данных

## Технологии

### Backend
- FastAPI: веб-фреймворк
- SQLAlchemy: ORM для работы с БД
- SQLite: база данных для workflow
- Pydantic: валидация данных
- bcrypt: хеширование паролей
- fast-bitrix24: библиотека для работы с Bitrix24 REST API (асинхронный клиент)

### Frontend
- React 19: UI библиотека
- TypeScript: типизация
- Vite: сборщик и dev-сервер
- Tailwind CSS: стилизация
- Zustand: управление состоянием
- React Router: роутинг
- Axios: HTTP клиент

## Безопасность

- Хеширование паролей через bcrypt
- Сессии через cookies с httpOnly флагом
- Валидация всех входных данных через Pydantic
- Проверка прав доступа (admin/user)
- Изоляция данных между workflow (отдельные БД)
- Публичный API endpoint доступен только по уникальному токену (без авторизации через сессию)
- Маппинг полей может создавать/удалять только admin
- API токен генерируется случайным образом через secrets.token_urlsafe
- Swagger UI (`/docs`) и ReDoc (`/redoc`) отключены по умолчанию для безопасности (включаются через переменную окружения `ENABLE_DOCS=true`)
- Все защищенные endpoints требуют авторизации через `get_current_user` dependency
- Webhook endpoint защищен через проверку домена и токена приложения (app_token)
- Контроль доступа к workflow: пользователь может получить доступ к workflow если он создал его, ему предоставлен доступ через user_workflow_access, или он является администратором

## Docker и развертывание

### Docker Compose
Приложение может быть запущено через Docker Compose для упрощения развертывания:
- `docker-compose.yml`: Конфигурация для запуска backend и frontend сервисов
- Backend сервис:
  - Порт: 7860
  - Использует `Dockerfile.backend` для сборки
  - Переменные окружения настраиваются через docker-compose.yml или .env файл
  - Volumes: монтирует `main.db` и директорию `workflows` для сохранения данных
- Frontend сервис:
  - Порт: 3012 (доступен извне)
  - Использует `Dockerfile.frontend` для сборки (multi-stage build с nginx)
  - Nginx проксирует запросы `/api` и `/api/public` на backend сервис
  - Статические файлы обслуживаются через nginx

### Переменные окружения
- `FRONTEND_URL`: URL фронтенда для генерации публичного API URL (по умолчанию: `http://localhost:3012`)
- `SECRET_KEY`: Секретный ключ для сессий (должен быть изменен в production)
- `ENABLE_DOCS`: Включить/выключить Swagger UI (по умолчанию: `false`)
- `CORS_ORIGINS`: Список разрешенных источников для CORS

### Публичный API через фронтенд
Публичный API endpoint доступен через фронтенд на порту 3012:
- URL формат: `{FRONTEND_URL}/api/public/workflows/{token}/leads`
- Nginx проксирует запросы `/api/public` на backend `/api/v1/public`
- В dev-режиме Vite также проксирует запросы на backend
- Backend генерирует `public_api_url` используя `FRONTEND_URL` вместо `base_url` из запроса

