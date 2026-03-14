#!/bin/bash
export DB_HOST=34.118.68.221
export DB_PORT=5432
export DB_USER=mes_user
export DB_PASSWORD=mes_app_password
export DB_NAME=mes_db
source .venv/bin/activate
alembic upgrade head

