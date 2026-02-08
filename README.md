# Database Backup Utility

A command-line tool for backing up and restoring **MySQL**, **PostgreSQL**, and **MongoDB** databases. Supports compression, AWS S3 cloud storage, logging, and Slack notifications.

> Built for the [roadmap.sh Database Backup Utility](https://roadmap.sh/projects/database-backup-utility) project.

## Features

- **Multi-database support** — MySQL, PostgreSQL, MongoDB
- **Connection testing** — validate credentials before operations
- **Backup** — full or selective (specific tables/collections)
- **Restore** — full or selective from backup files
- **Gzip compression** — reduce backup file sizes
- **AWS S3 integration** — upload/download backups to/from S3
- **Slack notifications** — get notified on backup completion/failure
- **Structured logging** — timestamped log files in `logs/`
- **Rich CLI output** — colored, formatted terminal output

## Installation

```bash
# Clone the repo
git clone https://github.com/meet1785/DBBackup.git
cd DBBackup

# Install in development mode
pip install -e .
```

### Prerequisites

The utility relies on native database CLI tools being available on your `PATH`:

| Database   | Required tools            |
|------------|---------------------------|
| MySQL      | `mysqldump`, `mysql`      |
| PostgreSQL | `pg_dump`, `psql`         |
| MongoDB    | `mongodump`, `mongorestore` |

Install them via your system's package manager (e.g., `apt install mysql-client postgresql-client mongodb-database-tools`).

## Usage

After installation, the `db-backup` command is available globally.

### Test Connection

```bash
db-backup test-connection \
  --db-type mysql \
  --host localhost \
  --port 3306 \
  --user root \
  --password mypassword \
  --database mydb
```

### Create a Backup

```bash
# Full backup with compression (default)
db-backup backup \
  --db-type mysql \
  --host localhost \
  --user root \
  --password mypassword \
  --database mydb \
  --dest ./backups

# Selective backup (specific tables)
db-backup backup \
  --db-type postgresql \
  --host localhost \
  --user postgres \
  --password secret \
  --database mydb \
  --tables "users,orders,products" \
  --dest ./backups

# Backup without compression
db-backup backup \
  --db-type mysql \
  --host localhost \
  --user root \
  --password secret \
  --database mydb \
  --no-compress

# Backup and upload to S3
db-backup backup \
  --db-type postgresql \
  --host localhost \
  --user postgres \
  --password secret \
  --database mydb \
  --s3-bucket my-backup-bucket \
  --s3-region us-east-1
```

### Restore a Backup

```bash
# Restore from a local backup
db-backup restore \
  --db-type mysql \
  --host localhost \
  --user root \
  --password mypassword \
  --database mydb \
  --backup-file ./backups/mysql_mydb_20260208_120000.sql.gz

# Restore specific tables
db-backup restore \
  --db-type postgresql \
  --host localhost \
  --user postgres \
  --password secret \
  --database mydb \
  --backup-file ./backups/pg_mydb_20260208_120000.sql \
  --tables "users,orders"

# Restore from S3
db-backup restore \
  --db-type mysql \
  --host localhost \
  --user root \
  --password secret \
  --database mydb \
  --backup-file ./backups/mysql_mydb_20260208.sql.gz \
  --s3-bucket my-backup-bucket \
  --s3-key mysql_mydb_20260208_120000.sql.gz
```

### Slack Notifications

Pass a webhook URL to receive Slack messages on backup/restore completion:

```bash
db-backup backup \
  --db-type mysql \
  --host localhost \
  --user root \
  --password secret \
  --database mydb \
  --slack-webhook https://hooks.slack.com/services/T.../B.../xxx

# Or set it via environment variable
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../xxx"
db-backup backup --db-type mysql --host localhost --user root --password secret --database mydb
```

### Help

```bash
db-backup --help
db-backup backup --help
db-backup restore --help
db-backup test-connection --help
```

## Project Structure

```
DBBackup/
├── db_backup/
│   ├── __init__.py            # Package version
│   ├── cli.py                 # CLI entry point (Click)
│   ├── compression.py         # Gzip compress/decompress
│   ├── logger.py              # Logging configuration
│   ├── notifications.py       # Slack notifications
│   ├── storage.py             # AWS S3 upload/download
│   └── connectors/
│       ├── __init__.py        # BaseConnector ABC
│       ├── mysql.py           # MySQL connector
│       ├── postgresql.py      # PostgreSQL connector
│       └── mongodb.py         # MongoDB connector
├── logs/                      # Generated log files
├── backups/                   # Default backup destination
├── pyproject.toml             # Project metadata & dependencies
└── README.md
```

## Configuration

All options are passed via CLI flags. Passwords can be entered interactively (prompted) if not passed as a flag.

### Environment Variables

| Variable            | Description                        |
|---------------------|------------------------------------|
| `SLACK_WEBHOOK_URL` | Default Slack webhook for notifications |
| `AWS_ACCESS_KEY_ID` | AWS credentials for S3 operations  |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for S3 operations |
| `AWS_DEFAULT_REGION`| Default AWS region                 |

## License

MIT