# Contributing to Panorama ConfigPump Plugin

Thank you for your interest in contributing to the Panorama ConfigPump Plugin! This guide explains how to set up your environment, run the project, develop features, and submit changes.

## Table of Contents
- [Development Setup](#development-setup)
- [Common Make Commands](#common-make-commands)
- [Testing](#testing)
- [Linting and Formatting](#linting-and-formatting)
- [Debugging](#debugging)
- [Contributing Workflow](#contributing-workflow)
- [Code of Conduct](#code-of-conduct)
- [Getting Help](#getting-help)

## Development Setup

### Prerequisites
- Git
- Docker and Docker Compose (recommended for running NetBox + plugin)
- [Poetry](https://python-poetry.org/) (optional; for local tooling like ruff/black/pre-commit)

### Quick start with Codespaces
1. Click the "Code" button on the repository and select "Create codespace on main".
2. In the terminal, run:
   ```bash
   make demo_environment
   ```
3. Open `http://localhost:8000` and log in with `admin/admin`.

### Local setup
1. Clone the repository:
   ```bash
   git clone https://github.com/rautanen-io/netbox-panorama-configpump-plugin.git
   cd netbox-panorama-configpump-plugin
   ```
2. (Optional) Install local tooling:
   ```bash
   poetry install
   ```
3. Start the development environment (first run builds and applies migrations):
   ```bash
   make debug
   ```
4. When NetBox finishes starting, press `Ctrl+C` once to stop.
5. Create a superuser:
   ```bash
   make createsuperuser
   ```
6. Start again:
   ```bash
   make debug
   ```
7. Visit `http://localhost:8000`.

## Common Make Commands
- `make build`: Build the NetBox + plugin images.
- `make debug`: Start services in the foreground (logs in terminal).
- `make start` / `make stop`: Start/stop services in the background.
- `make destroy`: Stop services and remove the project DB volume.
- `make createsuperuser`: Create a NetBox admin user.
- `make migrations`: Create Django migrations for the plugin.
- `make demo_environment`: Restore demo data and start services.

## Testing
Run tests inside the containerized environment:
```bash
make test
```
Faster iteration (stop on first failure):
```bash
make fasttest ARGS="<test_path_or_marker>"
```
Examples:
```bash
make fasttest ARGS='-k test_extract_templates_and_device_groups_from_config'
```

## Linting and Formatting
Use the pre-configured tools:
```bash
make lint     # ruff (lint) + black --check
make format   # ruff --fix + black
```
To enable Git hooks locally:
```bash
poetry run pre-commit install
poetry run pre-commit run --all-files
```

## Debugging

### VS Code configuration
Attach to the running NetBox process using this `launch.json` entry:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug Netbox",
            "type": "debugpy",
            "request": "attach",
            "connect": { "port": 3000, "host": "127.0.0.1" },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}/netbox_panorama_configpump_plugin",
                    "remoteRoot": "/opt/netbox_panorama_configpump_plugin/netbox_panorama_configpump_plugin"
                }
            ]
        }
    ]
}
```

## Contributing Workflow
1. Fork the repository and create a feature branch.
2. Make your changes in small, focused commits.
3. Add or update tests for any new behavior.
4. Run `make format`, `make lint`, and `make test` until green.
5. Update docs/user-facing texts if behavior changes.
6. Open a Pull Request with a clear description of the change and rationale.

## Code of Conduct
This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report any unacceptable behavior to [veikko@rautanen.io](mailto:veikko@rautanen.io).

## Getting Help
If you need assistance or have questions about contributing:
- Open an issue on GitHub
- Contact the maintainers at [veikko@rautanen.io](mailto:veikko@rautanen.io)
