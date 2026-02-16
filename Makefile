PACKAGES = ojs-django ojs-flask ojs-fastapi ojs-celery ojs-sqlalchemy

.PHONY: install-all test-all lint-all format-all clean

install-all:
	@for pkg in $(PACKAGES); do \
		echo "Installing $$pkg..."; \
		pip install -e "./$$pkg[dev]"; \
	done

test-all:
	@for pkg in $(PACKAGES); do \
		echo "Testing $$pkg..."; \
		cd $$pkg && pytest && cd ..; \
	done

lint-all:
	@for pkg in $(PACKAGES); do \
		echo "Linting $$pkg..."; \
		cd $$pkg && ruff check . && mypy src/ && cd ..; \
	done

format-all:
	@for pkg in $(PACKAGES); do \
		echo "Formatting $$pkg..."; \
		cd $$pkg && ruff format . && ruff check --fix . && cd ..; \
	done

clean:
	@for pkg in $(PACKAGES); do \
		rm -rf $$pkg/dist $$pkg/build $$pkg/*.egg-info $$pkg/src/*.egg-info; \
		rm -rf $$pkg/.pytest_cache $$pkg/.mypy_cache $$pkg/.ruff_cache; \
	done
	find . -type d -name __pycache__ -exec rm -rf {} +
