.PHONY: migrate
migrate:
	docker compose -f docker-compose.local.yml run --rm backend alembic upgrade head
