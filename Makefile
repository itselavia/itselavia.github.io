.PHONY: setup validate test test-flaky coverage docs format build serve rollback

setup:
	git config core.hooksPath .githooks
	@if command -v bundle >/dev/null 2>&1; then bundle install; fi
	python3 scripts/validate_site.py --check-format --check-docs
	python3 scripts/run_tests.py --check-coverage --repeat 2

validate:
	python3 scripts/validate_site.py --check-format --check-docs

test:
	python3 scripts/run_tests.py

test-flaky:
	python3 scripts/run_tests.py --repeat 3

coverage:
	python3 scripts/run_tests.py --check-coverage

docs:
	python3 scripts/validate_site.py --generate-docs

format:
	python3 scripts/validate_site.py --format

build:
	JEKYLL_ENV=production bundle exec jekyll build --baseurl "" --profile

serve:
	bundle exec jekyll serve --watch

rollback:
	@test -n "$(REF)" || (echo "Usage: make rollback REF=<commit-sha>" && exit 1)
	gh workflow run deploy.yml -f rollback_ref="$(REF)"
