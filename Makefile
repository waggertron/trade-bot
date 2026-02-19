COMPOSE = docker compose
SERVICES = backend frontend bot

.PHONY: help build up down restart stop start logs test \
        build-% up-% down-% restart-% stop-% start-% logs-% test-% \
        rebuild rebuild-% ps clean \
        dev-backend dev-frontend dev-bot \
        lint lint-fix typecheck typecheck-frontend lint-frontend lint-frontend-fix \
        format format-frontend check-deps dead-code check-all

help: ## Show this help
	@grep -E '^[a-zA-Z_%-]+:.*##' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Full stack
# ---------------------------------------------------------------------------

build: ## Build all containers
	$(COMPOSE) build

rebuild: ## Rebuild all containers from scratch (no cache)
	$(COMPOSE) build --no-cache

up: ## Start all containers (detached)
	$(COMPOSE) up -d

down: ## Stop and remove all containers
	$(COMPOSE) down

restart: ## Restart all containers
	$(COMPOSE) restart

stop: ## Stop all containers (keep state)
	$(COMPOSE) stop

start: ## Start stopped containers
	$(COMPOSE) start

logs: ## Tail logs for all containers
	$(COMPOSE) logs -f

ps: ## Show container status
	$(COMPOSE) ps

clean: ## Stop containers, remove volumes and images
	$(COMPOSE) down -v --rmi local

# ---------------------------------------------------------------------------
# Per-service  (usage: make build-backend, make logs-bot, etc.)
# ---------------------------------------------------------------------------

build-%: ## Build a single service (e.g. make build-backend)
	$(COMPOSE) build $*

rebuild-%: ## Rebuild a single service without cache (e.g. make rebuild-frontend)
	$(COMPOSE) build --no-cache $*

up-%: ## Start a single service (e.g. make up-bot)
	$(COMPOSE) up -d $*

down-%: ## Stop and remove a single service
	$(COMPOSE) rm -sf $*

restart-%: ## Restart a single service
	$(COMPOSE) restart $*

stop-%: ## Stop a single service
	$(COMPOSE) stop $*

start-%: ## Start a stopped service
	$(COMPOSE) start $*

logs-%: ## Tail logs for a single service
	$(COMPOSE) logs -f $*

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test: ## Run health checks against running containers
	@echo "--- Backend health ---"
	@curl -sf http://localhost:8080/api/health && echo " OK" || echo " FAIL"
	@echo "--- Frontend reachable ---"
	@curl -sf -o /dev/null http://localhost:3000 && echo " OK" || echo " FAIL"
	@echo "--- Bot running ---"
	@$(COMPOSE) ps bot --format '{{.State}}' | grep -q running && echo " OK" || echo " FAIL"

test-backend: ## Test backend health endpoint
	curl -sf http://localhost:8080/api/health | python3 -m json.tool

test-frontend: ## Test frontend is serving pages
	curl -sf -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3000

test-bot: ## Show recent bot logs
	$(COMPOSE) logs --tail=20 bot

# ---------------------------------------------------------------------------
# Local dev (outside containers)
# ---------------------------------------------------------------------------

dev-backend: ## Run backend locally (no container)
	uv run uvicorn src.dashboard.app:create_app --host 0.0.0.0 --port 8080 --factory --reload

dev-frontend: ## Run frontend locally (no container)
	cd web && npm run dev

dev-bot: ## Run trading bot locally (no container)
	uv run python main.py

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint: ## Python lint (ruff)
	uv run ruff check src/ tests/

lint-fix: ## Auto-fix Python lint
	uv run ruff check --fix src/ tests/

typecheck: ## Python type check (pyrefly)
	uv run pyrefly check src/

typecheck-frontend: ## Frontend type check (tsc)
	cd web && npx tsc --noEmit

lint-frontend: ## Frontend lint (biome)
	cd web && npx biome check ./src

lint-frontend-fix: ## Auto-fix frontend lint + format
	cd web && npx biome check --fix ./src

format: ## Format Python (ruff)
	uv run ruff format src/ tests/

format-frontend: ## Format frontend (biome)
	cd web && npx biome format --write ./src

check-deps: ## Check dependency hygiene (deptry)
	uv run deptry .

dead-code: ## Find dead Python code (vulture)
	uv run vulture src/ vulture_whitelist.py --min-confidence 80

check-all: ## Run ALL quality checks
	uv run ruff check src/ tests/
	uv run pyrefly check src/
	uv run deptry .
	uv run vulture src/ vulture_whitelist.py --min-confidence 80
	cd web && npx tsc --noEmit
	cd web && npx biome check ./src
