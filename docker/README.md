# FinSpectra Docker Deployment Guide

This directory contains containerization files for building and deploying the FinSpectra Autonomous Financial Crime Investigation platform using **Docker** and **Docker Compose**.

---

## 🚀 Quick Start (One Command Deployment)

To build and start all 4 services (**FastAPI Backend**, **React Frontend**, **PostgreSQL**, **Neo4j Graph Database**):

```bash
docker-compose up -d --build
```

---

## 📦 Container Services Architecture

| Service | Container Name | Port | Description |
| :--- | :--- | :--- | :--- |
| **Backend** | `finspectra-backend` | `8000` | FastAPI app, ML Isolation Forest, LangGraph `invest.planner` workflow, ReportLab PDF generator |
| **Frontend** | `finspectra-frontend` | `80` | Nginx serving production Vite React build with reverse proxy to `/api` |
| **Postgres** | `finspectra-postgres` | `5432` | PostgreSQL database for customer, account, transaction, and audit ledger persistence |
| **Neo4j** | `finspectra-neo4j` | `7474`, `7687` | Graph Database with APOC plugin for complex transaction network queries |

---

## 🛠️ Management Commands

### View Container Logs
```bash
docker-compose logs -f backend
```

### Stop All Services
```bash
docker-compose down
```

### Reset Database Volumes
```bash
docker-compose down -v
```

---

## 🌐 Local Development vs Docker

- **Local Dev (Lightweight)**: SQLite + NetworkX (No Docker required). Fast, zero external dependencies.
- **Docker Compose (Full Production)**: PostgreSQL + Neo4j + FastAPI + Nginx React Frontend.
