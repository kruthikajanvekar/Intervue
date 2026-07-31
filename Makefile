.PHONY: install run dev up down logs test lint clean

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api

test:
	pytest -v

lint:
	python -m py_compile $$(find app -name "*.py")

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf logs/*.log reports/*.pdf
