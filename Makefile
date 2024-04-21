all: help

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  lint                        to lint backend code (flake8)"

install:
	pip3 install -e .[dev]

lint:
	flake8 pytimefliplib --max-line-length=120 --ignore=N802