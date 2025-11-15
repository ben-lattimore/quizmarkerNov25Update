# Archive Directory

This directory contains historical configuration files that are no longer used in the active codebase but are kept for reference.

## Replit Configuration Files

### `.replit`
Original Replit IDE configuration file that defined how the application ran on the Replit platform. This file is no longer needed as the application has been migrated to run locally and will be deployed to Railway/Render for production.

### `replit.nix`
Nix package configuration file used by Replit to set up the runtime environment. This is Replit-specific and not needed for local development or production deployments.

## Migration Context

These files were archived during **Phase 1** of the migration plan (Foundation & Environment Setup) on **November 15, 2025**. The application was originally developed on Replit and is being migrated to a modern stack with:

- **Local Development**: PostgreSQL, virtual environment
- **Backend Hosting**: Railway
- **Frontend Hosting**: Vercel (future)
- **File Storage**: AWS S3 (future)

For current development setup instructions, see the main README.md file in the project root.
