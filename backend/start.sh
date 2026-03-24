#!/bin/bash
mkdir -p data/memory data/undo
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --reload
