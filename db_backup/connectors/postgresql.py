"""PostgreSQL database connector using pg_dump / psql CLI tools."""

import logging
import os
import subprocess
from datetime import datetime

from db_backup.connectors import BaseConnector

logger = logging.getLogger("db_backup")


class PostgreSQLConnector(BaseConnector):
    """Connector for PostgreSQL databases."""

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

    def _env(self) -> dict[str, str]:
        """Return env dict with PGPASSWORD set."""
        env = os.environ.copy()
        env["PGPASSWORD"] = self.password
        return env

    # ------------------------------------------------------------------ #
    #  Connection test
    # ------------------------------------------------------------------ #
    def test_connection(self) -> bool:
        try:
            import psycopg2

            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                dbname=self.database,
                connect_timeout=10,
            )
            conn.close()
            logger.info("PostgreSQL connection successful (%s@%s:%s/%s)", self.user, self.host, self.port, self.database)
            return True
        except Exception as exc:
            logger.error("PostgreSQL connection failed: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    #  Backup
    # ------------------------------------------------------------------ #
    def backup(self, dest_path: str, tables: list[str] | None = None) -> str:
        os.makedirs(dest_path, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pg_{self.database}_{timestamp}.sql"
        filepath = os.path.join(dest_path, filename)

        cmd = [
            "pg_dump",
            f"--host={self.host}",
            f"--port={self.port}",
            f"--username={self.user}",
            "--no-password",
            "--format=plain",
            "--verbose",
        ]

        if tables:
            for table in tables:
                cmd.extend([f"--table={table}"])

        cmd.append(self.database)

        logger.info("Running pg_dump for database '%s' ...", self.database)
        with open(filepath, "w") as out:
            result = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, text=True, env=self._env())

        if result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.error("pg_dump failed: %s", error_msg)
            raise RuntimeError(f"pg_dump failed: {error_msg}")

        size = os.path.getsize(filepath)
        logger.info("PostgreSQL backup created: %s (%s bytes)", filepath, size)
        return filepath

    # ------------------------------------------------------------------ #
    #  Restore
    # ------------------------------------------------------------------ #
    def restore(self, backup_file: str, tables: list[str] | None = None) -> None:
        if not os.path.isfile(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        cmd = [
            "psql",
            f"--host={self.host}",
            f"--port={self.port}",
            f"--username={self.user}",
            "--no-password",
            self.database,
        ]

        logger.info("Restoring PostgreSQL database '%s' from %s ...", self.database, backup_file)
        with open(backup_file, "r") as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, text=True, env=self._env())

        if result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.error("psql restore failed: %s", error_msg)
            raise RuntimeError(f"psql restore failed: {error_msg}")

        logger.info("PostgreSQL restore completed successfully.")
