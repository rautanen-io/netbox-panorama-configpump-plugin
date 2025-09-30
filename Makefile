NETBOX_VERSION?=4.3.7
PYTHON_VERSION?=3.11

COMPOSE_FILE=./develop/docker-compose.yml
BUILD_NAME=netbox-panorama-configpump-plugin
COMMON_PARAMS=--remove-orphans
PLUGIN_NAME=netbox_panorama_configpump_plugin

export NETBOX_VERSION := $(NETBOX_VERSION)
export PYTHON_VERSION := $(PYTHON_VERSION)

sources = netbox_panorama_configpump_plugin tests

.PHONY: test format lint unittest pre-commit clean seed-test-data

pre-commit:
	pre-commit run --all-files

clean:
	rm -rf *.egg-info
	rm -rf .tox dist site

build:
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} --profile netbox build \
		--build-arg NETBOX_VERSION=${NETBOX_VERSION} \
		--build-arg PYTHON_VERSION=${PYTHON_VERSION}

debug:
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} --profile netbox up ${COMMON_PARAMS}

start:
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} --profile netbox up -d ${COMMON_PARAMS}

stop:
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} --profile netbox down

destroy: stop
	docker volume rm -f ${BUILD_NAME}-postgres

bash:
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} run netbox /bin/bash

createsuperuser:
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} run netbox python manage.py createsuperuser

changepassword:
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} run netbox python manage.py changepassword admin

migrations:
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} \
		run netbox python manage.py makemigrations ${PLUGIN_NAME}

format:
	ruff check --fix $(sources)
	black $(sources)

lint:
	ruff check $(sources)
	black --check $(sources)

test: lint
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} run ${COMMON_PARAMS} netbox python manage.py \
		test --keepdb /opt/netbox_panorama_configpump_plugin

fasttest:
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} run ${COMMON_PARAMS}  netbox python manage.py \
		test --keepdb /opt/netbox_panorama_configpump_plugin --failfast $(ARGS)

take_snapshot:
	./develop/db_scripts/take_db_snapshot.sh

restore_snapshot:
	./develop/db_scripts/restore_db_snapshot.sh $(ARGS)

demo_environment:
	./develop/db_scripts/restore_db_snapshot.sh demo.Z
	docker compose -f ${COMPOSE_FILE} -p ${BUILD_NAME} --profile netbox up ${COMMON_PARAMS}
