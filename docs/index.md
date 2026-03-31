# NCLI Documentation

NCLI is a multi-vendor network device CLI built on [Netmiko](https://github.com/ktbyers/netmiko). It provides a unified interface for managing routers, switches, firewalls, and other network equipment across 150+ device types.

## Contents

- [Getting Started](getting-started.md) -- Installation, first inventory, first command
- [Inventory Schema](inventory-schema.md) -- YAML inventory format, defaults, groups, tags
- [CLI Reference](cli-reference.md) -- All commands, options, and exit codes
- [Configuration Management](configuration.md) -- Config push, diff, templates
- [Safety & Blocklists](safety.md) -- Command and config blocklists
- [Writing Inventory Plugins](plugins-inventory.md) -- Custom inventory sources
- [Writing Auth Plugins](plugins-auth.md) -- Custom credential backends
- [Architecture](architecture.md) -- Module layout, connection model, design decisions
- [Development](development.md) -- Setting up a dev environment, testing, linting, contributing
