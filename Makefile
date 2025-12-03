# Makefile for RePORTaLiN-Specialist Data Pipeline
# =================================================
#
# A clinical data processing pipeline for extraction, transformation,
# and de-identification of sensitive research data.
#
# Usage:
#   make              - Show help (default)
#   make run          - Run full pipeline
#   make install      - Install dependencies
#   make lint         - Run code quality checks
#   make test         - Run tests
#   make clean        - Remove generated files
#
# Configuration Variables:
#   PYTHON           - Python interpreter (auto-detected)
#   VENV_DIR         - Virtual environment directory (default: .venv)
#   PREFIX           - Installation prefix (default: /usr/local)
#
# Requirements:
#   - Python 3.10+ (auto-detected)
#   - pip (Python package installer)
#
# For more information, see README.md

# =============================================================================
# Special Targets (placed early per GNU Make recommendations)
# =============================================================================

# Delete targets if recipe fails
.DELETE_ON_ERROR:

# Don't delete intermediate files
.SECONDARY:

# Default goal
.DEFAULT_GOAL := help

# =============================================================================
# Shell Configuration
# =============================================================================

# Use bash with strict error handling
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# =============================================================================
# Configuration Variables (Simple Expansion for Performance)
# =============================================================================

# Project metadata
PROJECT_NAME := RePORTaLiN-Specialist
VERSION := $(shell grep "^__version__" __version__.py 2>/dev/null | head -1 | sed 's/.*"\(.*\)"/\1/' || echo "0.0.1")

# Color output (ANSI escape codes)
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
CYAN := \033[0;36m
BOLD := \033[1m
NC := \033[0m

# Installation prefix (can be overridden)
PREFIX ?= /usr/local

# =============================================================================
# Python Environment Detection
# =============================================================================

# Detect Python command (prefer python3)
PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)

# Virtual environment settings
VENV_DIR := .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

# Source directories
SRC_DIRS := scripts main.py config.py __version__.py

# Conditional Python command based on venv existence
ifeq ($(wildcard $(VENV_PYTHON)),)
    PYTHON_CMD := $(PYTHON)
    PIP_CMD := $(PYTHON) -m pip
    IN_VENV := false
else
    PYTHON_CMD := $(VENV_PYTHON)
    PIP_CMD := $(VENV_PIP)
    IN_VENV := true
endif

# =============================================================================
# Tool Validation
# =============================================================================

# Check for required tools at parse time
ifeq ($(PYTHON),)
    $(error Python is not installed or not in PATH. Please install Python 3.10+)
endif

# =============================================================================
# Phony Targets Declaration
# =============================================================================

.PHONY: help version info
.PHONY: venv install install-dev upgrade-deps
.PHONY: run run-verbose run-dictionary run-extract run-deidentify run-deidentify-verbose
.PHONY: lint format typecheck check-all test test-cov test-verbose
.PHONY: clean clean-cache clean-logs clean-results clean-venv distclean nuclear
.PHONY: commit check-commit bump-dry bump bump-patch bump-minor bump-major changelog hooks pre-commit

# =============================================================================
# Help Target
# =============================================================================

help:
	@printf "$(BOLD)$(BLUE)"
	@printf "╔═══════════════════════════════════════════════════════════════════╗\n"
	@printf "║         $(PROJECT_NAME) Data Pipeline - v$(VERSION)              ║\n"
	@printf "╚═══════════════════════════════════════════════════════════════════╝\n"
	@printf "$(NC)\n"
	@printf "$(BOLD)$(GREEN)Setup:$(NC)\n"
	@printf "  $(CYAN)make venv$(NC)            Create virtual environment\n"
	@printf "  $(CYAN)make install$(NC)         Install production dependencies\n"
	@printf "  $(CYAN)make install-dev$(NC)     Install development dependencies\n"
	@printf "  $(CYAN)make upgrade-deps$(NC)    Upgrade all dependencies\n"
	@printf "  $(CYAN)make version$(NC)         Show version information\n"
	@printf "  $(CYAN)make info$(NC)            Show environment information\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)Running:$(NC)\n"
	@printf "  $(CYAN)make run$(NC)             Run full pipeline (dictionary + extraction)\n"
	@printf "  $(CYAN)make run-verbose$(NC)     Run with verbose logging\n"
	@printf "  $(CYAN)make run-dictionary$(NC)  Run only dictionary loading\n"
	@printf "  $(CYAN)make run-extract$(NC)     Run only data extraction\n"
	@printf "  $(CYAN)make run-deidentify$(NC)  Run with de-identification\n"
	@printf "  $(CYAN)make run-deidentify-verbose$(NC)\n"
	@printf "                       De-identification with verbose logging\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)Code Quality:$(NC)\n"
	@printf "  $(CYAN)make lint$(NC)            Run ruff linter\n"
	@printf "  $(CYAN)make format$(NC)          Format code with ruff\n"
	@printf "  $(CYAN)make typecheck$(NC)       Run mypy type checker\n"
	@printf "  $(CYAN)make check-all$(NC)       Run all checks (lint + typecheck)\n"
	@printf "  $(CYAN)make test$(NC)            Run pytest\n"
	@printf "  $(CYAN)make test-cov$(NC)        Run pytest with coverage\n"
	@printf "  $(CYAN)make test-verbose$(NC)    Run pytest with verbose output\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)Cleaning:$(NC)\n"
	@printf "  $(CYAN)make clean$(NC)           Remove Python cache files\n"
	@printf "  $(CYAN)make clean-logs$(NC)      Remove log files\n"
	@printf "  $(CYAN)make clean-results$(NC)   Remove generated results (interactive)\n"
	@printf "  $(CYAN)make clean-venv$(NC)      Remove virtual environment\n"
	@printf "  $(CYAN)make distclean$(NC)       Remove all generated files\n"
	@printf "  $(CYAN)make nuclear$(NC)         $(RED)⚠ DANGER:$(NC) Remove EVERYTHING (interactive)\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)Versioning (Commitizen):$(NC)\n"
	@printf "  $(CYAN)make commit$(NC)          Interactive conventional commit\n"
	@printf "  $(CYAN)make bump$(NC)            Auto-bump version based on commits\n"
	@printf "  $(CYAN)make bump-dry$(NC)        Preview version bump (no changes)\n"
	@printf "  $(CYAN)make bump-patch$(NC)      Force PATCH bump (0.0.x)\n"
	@printf "  $(CYAN)make bump-minor$(NC)      Force MINOR bump (0.x.0)\n"
	@printf "  $(CYAN)make bump-major$(NC)      Force MAJOR bump (x.0.0)\n"
	@printf "  $(CYAN)make changelog$(NC)       Generate/update CHANGELOG.md\n"
	@printf "  $(CYAN)make hooks$(NC)           Install pre-commit hooks\n"
	@printf "  $(CYAN)make pre-commit$(NC)      Run all hooks on all files\n"
	@printf "\n"
	@printf "$(BOLD)$(YELLOW)Environment:$(NC)\n"
	@printf "  Python: $(PYTHON_CMD)\n"
	@printf "  Virtual env: $(if $(filter true,$(IN_VENV)),$(GREEN)active$(NC),$(YELLOW)not active$(NC))\n"
	@printf "\n"

# =============================================================================
# Information Targets
# =============================================================================

version:
	@$(PYTHON_CMD) main.py --version

info:
	@printf "$(BOLD)$(BLUE)Environment Information$(NC)\n"
	@printf "$(CYAN)─────────────────────────$(NC)\n"
	@printf "Project:     $(PROJECT_NAME)\n"
	@printf "Version:     $(VERSION)\n"
	@printf "Python:      $(PYTHON_CMD)\n"
	@printf "Python ver:  $$($(PYTHON_CMD) --version 2>&1)\n"
	@printf "Venv:        $(if $(filter true,$(IN_VENV)),$(GREEN)active$(NC) ($(VENV_DIR)),$(YELLOW)not active$(NC))\n"
	@printf "Shell:       $(SHELL)\n"
	@printf "Make:        $(MAKE_VERSION)\n"
	@printf "\n"

# =============================================================================
# Setup Targets
# =============================================================================

venv:
	@if [ -d "$(VENV_DIR)" ]; then \
		printf "$(YELLOW)⚠ Virtual environment already exists at $(VENV_DIR)$(NC)\n"; \
	else \
		printf "$(BLUE)Creating virtual environment...$(NC)\n"; \
		$(PYTHON) -m venv $(VENV_DIR); \
		printf "$(GREEN)✓ Virtual environment created at $(VENV_DIR)$(NC)\n"; \
		printf "$(YELLOW)→ Activate with: source $(VENV_DIR)/bin/activate$(NC)\n"; \
	fi

install:
	@printf "$(BLUE)Installing production dependencies...$(NC)\n"
	@$(PIP_CMD) install --upgrade pip --quiet
	@$(PIP_CMD) install -r requirements.txt --quiet
	@printf "$(GREEN)✓ Dependencies installed$(NC)\n"

install-dev: install
	@printf "$(BLUE)Installing development dependencies...$(NC)\n"
	@$(PIP_CMD) install -e ".[dev]" --quiet
	@printf "$(GREEN)✓ Development dependencies installed$(NC)\n"

upgrade-deps:
	@printf "$(BLUE)Upgrading all dependencies...$(NC)\n"
	@$(PIP_CMD) install --upgrade pip
	@$(PIP_CMD) install --upgrade -r requirements.txt
	@printf "$(GREEN)✓ Dependencies upgraded$(NC)\n"

# =============================================================================
# Pipeline Execution Targets
# =============================================================================

run:
	@printf "$(BLUE)Running pipeline...$(NC)\n"
	@$(PYTHON_CMD) main.py
	@printf "$(GREEN)✓ Pipeline complete$(NC)\n"

run-verbose:
	@printf "$(BLUE)Running pipeline (verbose)...$(NC)\n"
	@$(PYTHON_CMD) main.py --verbose
	@printf "$(GREEN)✓ Pipeline complete$(NC)\n"

run-dictionary:
	@printf "$(BLUE)Running dictionary loading only...$(NC)\n"
	@$(PYTHON_CMD) main.py --skip-extraction
	@printf "$(GREEN)✓ Dictionary loading complete$(NC)\n"

run-extract:
	@printf "$(BLUE)Running data extraction only...$(NC)\n"
	@$(PYTHON_CMD) main.py --skip-dictionary
	@printf "$(GREEN)✓ Data extraction complete$(NC)\n"

run-deidentify:
	@printf "$(BLUE)Running pipeline with de-identification...$(NC)\n"
	@$(PYTHON_CMD) main.py --enable-deidentification
	@printf "$(GREEN)✓ De-identification complete$(NC)\n"

run-deidentify-verbose:
	@printf "$(BLUE)Running pipeline with de-identification (verbose)...$(NC)\n"
	@$(PYTHON_CMD) main.py --enable-deidentification --verbose
	@printf "$(GREEN)✓ De-identification complete$(NC)\n"

# =============================================================================
# Code Quality Targets
# =============================================================================

lint:
	@printf "$(BLUE)Running ruff linter...$(NC)\n"
	@$(PYTHON_CMD) -m ruff check $(SRC_DIRS)
	@printf "$(GREEN)✓ Lint passed$(NC)\n"

format:
	@printf "$(BLUE)Formatting code with ruff...$(NC)\n"
	@$(PYTHON_CMD) -m ruff format $(SRC_DIRS)
	@$(PYTHON_CMD) -m ruff check --fix $(SRC_DIRS)
	@printf "$(GREEN)✓ Formatting complete$(NC)\n"

typecheck:
	@printf "$(BLUE)Running mypy type checker...$(NC)\n"
	@$(PYTHON_CMD) -m mypy $(SRC_DIRS)
	@printf "$(GREEN)✓ Type check passed$(NC)\n"

check-all: lint typecheck
	@printf "$(GREEN)✓ All checks passed$(NC)\n"

# =============================================================================
# Testing Targets
# =============================================================================

test:
	@printf "$(BLUE)Running tests...$(NC)\n"
	@$(PYTHON_CMD) -m pytest
	@printf "$(GREEN)✓ Tests passed$(NC)\n"

test-verbose:
	@printf "$(BLUE)Running tests (verbose)...$(NC)\n"
	@$(PYTHON_CMD) -m pytest -v
	@printf "$(GREEN)✓ Tests passed$(NC)\n"

test-cov:
	@printf "$(BLUE)Running tests with coverage...$(NC)\n"
	@$(PYTHON_CMD) -m pytest --cov=scripts --cov-report=term-missing --cov-report=html
	@printf "$(GREEN)✓ Tests passed. Coverage report: htmlcov/index.html$(NC)\n"

# =============================================================================
# Cleaning Targets
# =============================================================================

clean: clean-cache
	@printf "$(GREEN)✓ Clean complete$(NC)\n"

clean-cache:
	@printf "$(BLUE)Cleaning cache files...$(NC)\n"
	-@find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null
	-@find . -type f -name "*.pyc" -delete 2>/dev/null
	-@find . -type f -name "*.pyo" -delete 2>/dev/null
	-@find . -type f -name ".DS_Store" -delete 2>/dev/null
	-@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
	-@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null
	-@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null
	-@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null
	-@rm -rf htmlcov/ .coverage 2>/dev/null

clean-logs:
	@printf "$(BLUE)Cleaning log files...$(NC)\n"
	-@rm -rf .logs/
	@printf "$(GREEN)✓ Logs cleaned$(NC)\n"

clean-results:
	@printf "$(RED)$(BOLD)WARNING: This will delete all results!$(NC)\n"
	@printf "Press Enter to continue or Ctrl+C to cancel... " && read _confirm
	-@rm -rf results/
	@printf "$(GREEN)✓ Results cleaned$(NC)\n"

clean-venv:
	@printf "$(BLUE)Removing virtual environment...$(NC)\n"
	-@rm -rf $(VENV_DIR)
	@printf "$(GREEN)✓ Virtual environment removed$(NC)\n"

distclean: clean clean-logs clean-venv
	@printf "$(RED)Cleaning all generated files...$(NC)\n"
	-@rm -rf results/
	-@rm -rf build/ dist/
	@printf "$(GREEN)✓ All generated files removed$(NC)\n"

# -----------------------------------------------------------------------------
# Nuclear Clean Target (DANGER: Removes everything including IDE configs)
# -----------------------------------------------------------------------------
# This target performs an extensive cleanup that removes ALL generated files,
# caches, virtual environments, IDE configurations, and results.
# Use with extreme caution - this is irreversible!
#
# Files/Directories removed:
#   - All Python caches (__pycache__, *.pyc, *.pyo)
#   - All tool caches (.pytest_cache, .mypy_cache, .ruff_cache)
#   - Virtual environment (.venv)
#   - IDE configurations (.vscode, .idea)
#   - Build artifacts (build, dist, *.egg-info)
#   - Coverage reports (htmlcov, .coverage)
#   - Log files (.logs)
#   - Results directory (results)
#   - Temporary files (tmp, .tmp, *.tmp)
#   - macOS metadata (.DS_Store)
# -----------------------------------------------------------------------------

nuclear:
	@printf "\n"
	@printf "$(RED)$(BOLD)╔═══════════════════════════════════════════════════════════════════╗$(NC)\n"
	@printf "$(RED)$(BOLD)║                    ⚠  NUCLEAR CLEAN WARNING  ⚠                    ║$(NC)\n"
	@printf "$(RED)$(BOLD)╚═══════════════════════════════════════════════════════════════════╝$(NC)\n"
	@printf "\n"
	@printf "$(YELLOW)This will permanently delete:$(NC)\n"
	@printf "  • Virtual environment (.venv)\n"
	@printf "  • IDE configurations (.vscode, .idea)\n"
	@printf "  • All cache files and directories\n"
	@printf "  • Build artifacts and distributions\n"
	@printf "  • Log files and coverage reports\n"
	@printf "  • Results and temporary files\n"
	@printf "\n"
	@printf "$(RED)$(BOLD)This action is IRREVERSIBLE!$(NC)\n"
	@printf "\n"
	@printf "$(YELLOW)Are you sure you want to proceed? [y/N]: $(NC)" && \
	read -r confirm && \
	case "$$confirm" in \
		[yY]|[yY][eE][sS]) \
			printf "\n$(RED)$(BOLD)☢ Initiating nuclear clean...$(NC)\n\n"; \
			printf "$(BLUE)Removing Python caches...$(NC)\n"; \
			find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true; \
			find . -type f -name "*.pyc" -delete 2>/dev/null || true; \
			find . -type f -name "*.pyo" -delete 2>/dev/null || true; \
			printf "$(BLUE)Removing tool caches...$(NC)\n"; \
			rm -rf .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true; \
			printf "$(BLUE)Removing virtual environment...$(NC)\n"; \
			rm -rf $(VENV_DIR) 2>/dev/null || true; \
			printf "$(BLUE)Removing IDE configurations...$(NC)\n"; \
			rm -rf .vscode .idea 2>/dev/null || true; \
			printf "$(BLUE)Removing build artifacts...$(NC)\n"; \
			rm -rf build dist 2>/dev/null || true; \
			find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true; \
			printf "$(BLUE)Removing coverage reports...$(NC)\n"; \
			rm -rf htmlcov .coverage 2>/dev/null || true; \
			printf "$(BLUE)Removing log files...$(NC)\n"; \
			rm -rf .logs 2>/dev/null || true; \
			printf "$(BLUE)Removing results...$(NC)\n"; \
			rm -rf results 2>/dev/null || true; \
			printf "$(BLUE)Removing temporary files...$(NC)\n"; \
			rm -rf tmp .tmp 2>/dev/null || true; \
			find . -type f -name "*.tmp" -delete 2>/dev/null || true; \
			printf "$(BLUE)Removing macOS metadata...$(NC)\n"; \
			find . -type f -name ".DS_Store" -delete 2>/dev/null || true; \
			printf "\n$(GREEN)$(BOLD)☢ Nuclear clean complete!$(NC)\n"; \
			printf "$(YELLOW)→ Run 'make venv && make install-dev' to rebuild environment$(NC)\n\n"; \
			;; \
		*) \
			printf "\n$(GREEN)✓ Nuclear clean aborted. No files were removed.$(NC)\n\n"; \
			;; \
	esac

# =============================================================================
# Version Management (Commitizen)
# =============================================================================
# Automatic semantic versioning based on conventional commits:
#   - fix:  -> PATCH bump (0.0.x)
#   - feat: -> MINOR bump (0.x.0)
#   - BREAKING CHANGE: or feat!/fix!: -> MAJOR bump (x.0.0)

# Interactive commit with conventional format
commit:
	@printf "$(BLUE)Starting interactive commit...$(NC)\n"
	@$(VENV_DIR)/bin/cz commit

# Check if commit message follows conventional format
check-commit:
	@printf "$(BLUE)Checking last commit message...$(NC)\n"
	@$(VENV_DIR)/bin/cz check --rev-range HEAD~1..HEAD
	@printf "$(GREEN)✓ Commit message is valid$(NC)\n"

# Auto-bump version based on commits (dry-run first)
bump-dry:
	@printf "$(BLUE)Dry-run version bump (no changes)...$(NC)\n"
	@$(VENV_DIR)/bin/cz bump --dry-run

# Auto-bump version and create tag
bump:
	@printf "$(BLUE)Bumping version based on commits...$(NC)\n"
	@$(VENV_DIR)/bin/cz bump
	@printf "$(GREEN)✓ Version bumped! Check git log for new tag.$(NC)\n"

# Force specific version bumps
bump-patch:
	@printf "$(BLUE)Bumping PATCH version...$(NC)\n"
	@$(VENV_DIR)/bin/cz bump --increment PATCH
	@printf "$(GREEN)✓ Patch version bumped$(NC)\n"

bump-minor:
	@printf "$(BLUE)Bumping MINOR version...$(NC)\n"
	@$(VENV_DIR)/bin/cz bump --increment MINOR
	@printf "$(GREEN)✓ Minor version bumped$(NC)\n"

bump-major:
	@printf "$(BLUE)Bumping MAJOR version...$(NC)\n"
	@$(VENV_DIR)/bin/cz bump --increment MAJOR
	@printf "$(GREEN)✓ Major version bumped$(NC)\n"

# Generate/update changelog
changelog:
	@printf "$(BLUE)Generating changelog...$(NC)\n"
	@$(VENV_DIR)/bin/cz changelog
	@printf "$(GREEN)✓ Changelog updated$(NC)\n"

# Install pre-commit hooks
hooks:
	@printf "$(BLUE)Installing pre-commit hooks...$(NC)\n"
	@$(VENV_DIR)/bin/pre-commit install --hook-type commit-msg --hook-type pre-commit
	@printf "$(GREEN)✓ Pre-commit hooks installed$(NC)\n"

# Run all pre-commit hooks on all files
pre-commit:
	@printf "$(BLUE)Running pre-commit hooks on all files...$(NC)\n"
	@$(VENV_DIR)/bin/pre-commit run --all-files

# =============================================================================
# End of Makefile
# =============================================================================
