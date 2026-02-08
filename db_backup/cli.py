"""CLI entry point for the Database Backup Utility."""

import os
import sys
import time
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from db_backup import __version__
from db_backup.compression import compress_file, decompress_file
from db_backup.logger import logger
from db_backup.notifications import send_slack_notification
from db_backup.storage import download_from_s3, upload_to_s3

console = Console()

DB_TYPES = ("mysql", "postgresql", "mongodb")


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

def _get_connector(db_type: str, host: str, port: int, user: str, password: str, database: str):
    """Factory: return the correct connector instance."""
    if db_type == "mysql":
        from db_backup.connectors.mysql import MySQLConnector
        return MySQLConnector(host, port, user, password, database)
    elif db_type == "postgresql":
        from db_backup.connectors.postgresql import PostgreSQLConnector
        return PostgreSQLConnector(host, port, user, password, database)
    elif db_type == "mongodb":
        from db_backup.connectors.mongodb import MongoDBConnector
        return MongoDBConnector(host, port, user, password, database)
    else:
        raise click.BadParameter(f"Unsupported database type: {db_type}")


def _default_port(db_type: str) -> int:
    return {"mysql": 3306, "postgresql": 5432, "mongodb": 27017}.get(db_type, 0)


# ------------------------------------------------------------------ #
#  CLI group
# ------------------------------------------------------------------ #

@click.group()
@click.version_option(__version__, prog_name="db-backup")
def cli():
    """Database Backup Utility — back up and restore MySQL, PostgreSQL & MongoDB databases."""
    pass


# ------------------------------------------------------------------ #
#  BACKUP command
# ------------------------------------------------------------------ #

@cli.command()
@click.option("--db-type", required=True, type=click.Choice(DB_TYPES, case_sensitive=False), help="Database type.")
@click.option("--host", default="localhost", show_default=True, help="Database host.")
@click.option("--port", default=None, type=int, help="Database port (defaults per DB type).")
@click.option("--user", required=True, help="Database username.")
@click.option("--password", required=True, prompt=True, hide_input=True, help="Database password.")
@click.option("--database", required=True, help="Database name.")
@click.option("--tables", default=None, help="Comma-separated list of tables/collections to back up (selective backup).")
@click.option("--compress/--no-compress", default=True, show_default=True, help="Compress the backup file with gzip.")
@click.option("--dest", default="./backups", show_default=True, help="Local directory to store the backup.")
@click.option("--s3-bucket", default=None, help="AWS S3 bucket name (upload backup to S3).")
@click.option("--s3-key", default=None, help="S3 object key (defaults to filename).")
@click.option("--s3-region", default=None, help="AWS region for S3.")
@click.option("--slack-webhook", default=None, envvar="SLACK_WEBHOOK_URL", help="Slack webhook URL for notifications.")
def backup(db_type, host, port, user, password, database, tables, compress, dest, s3_bucket, s3_key, s3_region, slack_webhook):
    """Create a database backup."""
    if port is None:
        port = _default_port(db_type)

    table_list = [t.strip() for t in tables.split(",")] if tables else None

    console.print(f"\n[bold cyan]Database Backup Utility v{__version__}[/bold cyan]")
    console.print(f"  DB Type   : {db_type}")
    console.print(f"  Host      : {host}:{port}")
    console.print(f"  Database  : {database}")
    console.print(f"  Tables    : {table_list or 'ALL'}")
    console.print(f"  Compress  : {compress}")
    console.print(f"  Dest      : {dest}")
    if s3_bucket:
        console.print(f"  S3 Bucket : {s3_bucket}")
    console.print()

    # 1. Test connection
    connector = _get_connector(db_type, host, port, user, password, database)
    with console.status("[bold green]Testing database connection..."):
        if not connector.test_connection():
            console.print("[bold red]Connection failed.[/bold red] Check your credentials and try again.")
            sys.exit(1)
    console.print("[green]✓[/green] Connection verified.\n")

    # 2. Run backup
    start = time.time()
    try:
        with console.status("[bold green]Creating backup..."):
            backup_file = connector.backup(dest, tables=table_list)
    except Exception as exc:
        elapsed = time.time() - start
        logger.error("Backup failed after %.1fs: %s", elapsed, exc)
        _notify_slack(slack_webhook, db_type, database, "FAILED", elapsed, str(exc))
        console.print(f"[bold red]Backup failed:[/bold red] {exc}")
        sys.exit(1)

    # 3. Compress
    if compress:
        backup_file = compress_file(backup_file)

    elapsed = time.time() - start

    # 4. Upload to S3
    s3_uri = None
    if s3_bucket:
        try:
            s3_uri = upload_to_s3(backup_file, s3_bucket, key=s3_key, region=s3_region)
        except Exception as exc:
            logger.error("S3 upload failed: %s", exc)
            console.print(f"[bold red]S3 upload failed:[/bold red] {exc}")

    # 5. Summary
    _print_summary(backup_file, elapsed, s3_uri)

    # 6. Slack notification
    _notify_slack(slack_webhook, db_type, database, "SUCCESS", elapsed, backup_file)


# ------------------------------------------------------------------ #
#  RESTORE command
# ------------------------------------------------------------------ #

@cli.command()
@click.option("--db-type", required=True, type=click.Choice(DB_TYPES, case_sensitive=False), help="Database type.")
@click.option("--host", default="localhost", show_default=True, help="Database host.")
@click.option("--port", default=None, type=int, help="Database port (defaults per DB type).")
@click.option("--user", required=True, help="Database username.")
@click.option("--password", required=True, prompt=True, hide_input=True, help="Database password.")
@click.option("--database", required=True, help="Database name to restore into.")
@click.option("--backup-file", required=True, type=click.Path(exists=False), help="Path to the backup file.")
@click.option("--tables", default=None, help="Comma-separated tables/collections for selective restore.")
@click.option("--s3-bucket", default=None, help="Download backup from this S3 bucket first.")
@click.option("--s3-key", default=None, help="S3 object key of the backup file.")
@click.option("--s3-region", default=None, help="AWS region for S3.")
@click.option("--slack-webhook", default=None, envvar="SLACK_WEBHOOK_URL", help="Slack webhook URL for notifications.")
def restore(db_type, host, port, user, password, database, backup_file, tables, s3_bucket, s3_key, s3_region, slack_webhook):
    """Restore a database from a backup file."""
    if port is None:
        port = _default_port(db_type)

    table_list = [t.strip() for t in tables.split(",")] if tables else None

    console.print(f"\n[bold cyan]Database Restore — v{__version__}[/bold cyan]")
    console.print(f"  DB Type   : {db_type}")
    console.print(f"  Host      : {host}:{port}")
    console.print(f"  Database  : {database}")
    console.print(f"  Backup    : {backup_file}")
    console.print(f"  Tables    : {table_list or 'ALL'}")
    console.print()

    # 1. Download from S3 if needed
    if s3_bucket and s3_key:
        console.print("[bold green]Downloading backup from S3...[/bold green]")
        backup_file = download_from_s3(s3_bucket, s3_key, backup_file, region=s3_region)

    # 2. Decompress if .gz
    if backup_file.endswith(".gz"):
        backup_file = decompress_file(backup_file)

    if not os.path.isfile(backup_file):
        console.print(f"[bold red]File not found:[/bold red] {backup_file}")
        sys.exit(1)

    # 3. Test connection
    connector = _get_connector(db_type, host, port, user, password, database)
    with console.status("[bold green]Testing database connection..."):
        if not connector.test_connection():
            console.print("[bold red]Connection failed.[/bold red] Check your credentials and try again.")
            sys.exit(1)
    console.print("[green]✓[/green] Connection verified.\n")

    # 4. Restore
    start = time.time()
    try:
        with console.status("[bold green]Restoring database..."):
            connector.restore(backup_file, tables=table_list)
    except Exception as exc:
        elapsed = time.time() - start
        logger.error("Restore failed after %.1fs: %s", elapsed, exc)
        _notify_slack(slack_webhook, db_type, database, "RESTORE FAILED", elapsed, str(exc))
        console.print(f"[bold red]Restore failed:[/bold red] {exc}")
        sys.exit(1)

    elapsed = time.time() - start
    console.print(f"\n[bold green]✓ Restore completed in {elapsed:.1f}s[/bold green]")
    _notify_slack(slack_webhook, db_type, database, "RESTORE SUCCESS", elapsed, backup_file)


# ------------------------------------------------------------------ #
#  TEST-CONNECTION command
# ------------------------------------------------------------------ #

@cli.command("test-connection")
@click.option("--db-type", required=True, type=click.Choice(DB_TYPES, case_sensitive=False), help="Database type.")
@click.option("--host", default="localhost", show_default=True, help="Database host.")
@click.option("--port", default=None, type=int, help="Database port.")
@click.option("--user", required=True, help="Database username.")
@click.option("--password", required=True, prompt=True, hide_input=True, help="Database password.")
@click.option("--database", required=True, help="Database name.")
def test_connection(db_type, host, port, user, password, database):
    """Test database connectivity."""
    if port is None:
        port = _default_port(db_type)

    connector = _get_connector(db_type, host, port, user, password, database)
    if connector.test_connection():
        console.print(f"[bold green]✓ Successfully connected to {db_type} at {host}:{port}/{database}[/bold green]")
    else:
        console.print(f"[bold red]✗ Failed to connect to {db_type} at {host}:{port}/{database}[/bold red]")
        sys.exit(1)


# ------------------------------------------------------------------ #
#  Printing / notification helpers
# ------------------------------------------------------------------ #

def _print_summary(backup_file: str, elapsed: float, s3_uri: str | None = None):
    """Print a summary table after a backup."""
    tbl = Table(title="Backup Summary", show_header=False, border_style="green")
    tbl.add_column("Key", style="bold")
    tbl.add_column("Value")
    tbl.add_row("File", backup_file)
    tbl.add_row("Size", _human_size(os.path.getsize(backup_file)))
    tbl.add_row("Duration", f"{elapsed:.1f}s")
    if s3_uri:
        tbl.add_row("S3 URI", s3_uri)
    tbl.add_row("Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    console.print()
    console.print(tbl)
    console.print()


def _human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def _notify_slack(webhook: str | None, db_type: str, database: str, status: str, elapsed: float, detail: str):
    """Send a Slack notification about the operation."""
    if not webhook:
        return
    icon = ":white_check_mark:" if "SUCCESS" in status else ":x:"
    msg = (
        f"{icon} *DB Backup — {status}*\n"
        f"• Database: `{db_type}` / `{database}`\n"
        f"• Duration: {elapsed:.1f}s\n"
        f"• Detail: {detail}\n"
        f"• Time: {datetime.now():%Y-%m-%d %H:%M:%S}"
    )
    send_slack_notification(webhook, msg)


if __name__ == "__main__":
    cli()
