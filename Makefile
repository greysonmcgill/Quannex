.PHONY: dev api frontend migrate seed install status test lint

dev:
	python3 -m quan.cli start

api:
	python3 -m quan.cli api

frontend:
	python3 -m quan.cli dashboard

migrate:
	python3 -m quan.cli db migrate

seed:
	python3 -m quan.cli db seed --reset

install:
	python3 -m quan.cli install

status:
	python3 -m quan.cli status

test:
	python3 -m quan.cli test --coverage

lint:
	python3 -m quan.cli lint
