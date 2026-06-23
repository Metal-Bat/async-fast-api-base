# Async FastAPI Sample (Modern Backend Template)

A **production-ready FastAPI template** designed for scalability, observability, and clean architecture.

It demonstrates a modern Python backend stack using:

* Clean Architecture (DDD-inspired)
* Docker-first development
* Observability (OpenTelemetry + Jaeger)
* Strong typing & linting (Ruff + Ty)
* Modern tooling (uv + mise)
* Fully automated dev workflow

---

## ✨ Features

* ⚡ FastAPI (async-first API framework)
* 🧱 Clean Architecture (domain / application / data / presentation)
* 🐘 PostgreSQL (asyncpg + SQLAlchemy 2 + SQLModel)
* 🔁 Alembic migrations
* 📦 Dockerize full stack (backend + postgres + observability stack)
* 📊 OpenTelemetry tracing (FastAPI + collector + Jaeger)
* 🧠 Strong typing (Ty)
* 🧹 Ruff for linting + formatting
* 🧪 Pytest + coverage + benchmarking
* 🔐 Security scanning (bandit + detect-secrets)
* 🧾 Conventional commits (Commitizen)
* 🚀 Developer experience via `mise`

---

## 🏗️ Architecture

This project follows a **modular domain-driven structure**:

```bash

src/
├── apps/
│   └── users/
│       ├── domain/         # Entities + DTOs (pure business logic)
│       ├── application/    # Use cases / services
│       ├── data/           # Repositories / DB layer
│       └── presentation/   # API routes (FastAPI)
│
├── core/
│   ├── settings.py
│   ├── base_service.py
│   ├── base_repository.py
│   └── deps.py
│
├── utils/
│   ├── logging_config.py
│   ├── middleware.py
│   ├── exceptions.py
│   └── pagination.py
│
├── migrations/            # Alembic migrations
└── main.py
```

---

## 🚀 Quick Start

### 1. Install tooling

This project uses `mise`:

```bash
mise install
```

---

### 2. Setup environment

```bash
mise run setup
```

This will:

* Install dependencies (uv)
* Setup pre-commit hooks

---

### 3. Start infrastructure

```bash
mise run up
```

This starts:

* Backend API
* PostgreSQL
* Observability stack (Jaeger + OpenTelemetry collector)

---

### 4. Run migrations

```bash
mise run migrate
```

---

### 5. Start development

```bash
mise run logs
```

or run backend shell:

```bash
mise run shell
```

---

## 📚 API Documentation

Once backend is running:

### Swagger UI

```bash
mise run swagger
```

👉 [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Testing

Run all tests:

```bash
mise run test
```

Run with coverage:

```bash
mise run coverage
```

Output:

* Terminal coverage report
* HTML report → `htmlcov/index.html`

---

## 📊 Benchmarking

Run performance benchmarks:

```bash
mise run benchmark
```

---

## 🔐 Security

Run security checks:

```bash
mise run security
```

Includes:

* Bandit (static security analysis)
* Detect-secrets (secret scanning)

---

## 🧹 Code Quality

### Format code

```bash
mise run fmt
```

### Lint code

```bash
mise run lint
```

### Fix lint issues

```bash
mise run lint-fix
```

### Type check

```bash
mise run typecheck
```

### Full check

```bash
mise run check
```

---

## 🐳 Docker Workflow

### Start everything

```bash
mise run up
```

### Stop everything

```bash
mise run down
```

### Rebuild

```bash
mise run rebuild
```

### Logs

```bash
mise run logs
```

### Shell into backend

```bash
mise run shell
```

---

## 🗄️ Database

### Run migrations

```bash
mise run migrate
```

### Create migration

```bash
mise run makemigrations -m "your message"
```

### Check migrations

```bash
mise run db-current
mise run db-history
```

---

## 🧠 Observability

This project includes full distributed tracing:

* OpenTelemetry SDK
* FastAPI instrumentation
* OTEL Collector
* Jaeger UI

Access Jaeger:

👉 [http://localhost:16686](http://localhost:16686)

---

## 🧾 Commit Workflow

This project enforces **Conventional Commits**.

### Interactive commit

```bash
mise run commit
```

### Version bump + changelog

```bash
mise run bump
```

---

## 🧪 CI Pipeline (Local)

Simulate CI locally:

```bash
mise run ci
```

Runs:

* formatting
* linting
* typing
* tests
* security checks

---

## 🧰 Tech Stack

| Layer         | Tech                   |
| ------------- | ---------------------- |
| API           | FastAPI                |
| DB            | PostgreSQL             |
| ORM           | SQLAlchemy + SQLModel  |
| Migrations    | Alembic                |
| Observability | OpenTelemetry + Jaeger |
| Validation    | Pydantic v2            |
| Typing        | Ty                     |
| Linting       | Ruff                   |
| Testing       | Pytest                 |
| Runtime       | Uvicorn                |
| Packaging     | uv                     |
| Dev UX        | mise                   |

---

## 📦 Project Philosophy

This template is built around:

* **Predictable structure**
* **Zero hidden magic**
* **Fast local iteration**
* **Production parity with Docker**
* **Strict typing + linting**
* **Observability by default**

---

## 🧪 Example Endpoint Structure

```bash
users/
├── domain/        → pure logic
├── application/   → use cases
├── data/          → DB layer
└── presentation/  → API routes
```

Each layer is independent → easy testing, scaling, and refactoring.

---

## 🧼 Notes

* No global dependencies (everything via `uv`)
* No Node required
* Fully reproducible environments
* Designed for scaling into microservices
