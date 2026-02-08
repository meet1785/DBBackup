"""MySQL database connector using mysqldump / mysql CLI tools."""

import logging
import os
import subprocess
from datetime import datetime

from db_backup.connectors import BaseConnector

logger = logging.getLogger("db_backup")


class MySQLConnector(BaseConnector):
    """Connector for MySQL / MariaDB databases."""

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

    # ------------------------------------------------------------------ #
    #  Connection test
    # ------------------------------------------------------------------ #
    def test_connection(self) -> bool:
        """Verify that we can connect to MySQL."""
        try:
            import pymysql

            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                connect_timeout=10,
            )
            conn.close()
            logger.info("MySQL connection successful (%s@%s:%s/%s)", self.user, self.host, self.port, self.database)
            return True
        except Exception as exc:
            logger.error("MySQL connection failed: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    #  Backup
    # ------------------------------------------------------------------ #
    def backup(self, dest_path: str, tables: list[str] | None = None) -> str:
        os.makedirs(dest_path, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mysql_{self.database}_{timestamp}.sql"
        filepath = os.path.join(dest_path, filename)

        cmd = [
            "sudo",
            "mysqldump",
            f"--host={self.host}",
            f"--port={self.port}",
            f"--user={self.user}",
            f"--password={self.password}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            self.database,
        ]

        if tables:
            cmd.extend(tables)

        logger.info("Running mysqldump for database '%s' ...", self.database)
        with open(filepath, "w") as out:
            result = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.error("mysqldump failed: %s", error_msg)
            raise RuntimeError(f"mysqldump failed: {error_msg}")

        size = os.path.getsize(filepath)
        logger.info("MySQL backup created: %s (%s bytes)", filepath, size)
        return filepath

    # ------------------------------------------------------------------ #
    #  Restore
    # ------------------------------------------------------------------ #
    def restore(self, backup_file: str, tables: list[str] | None = None) -> None:
        if not os.path.isfile(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        cmd = [
            "sudo",
            "mysql",
            f"--host={self.host}",
            f"--port={self.port}",
            f"--user={self.user}",
            f"--password={self.password}",
            self.database,
        ]

        logger.info("Restoring MySQL database '%s' from %s ...", self.database, backup_file)
        with open(backup_file, "r") as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.error("MySQL restore failed: %s", error_msg)
            raise RuntimeError(f"MySQL restore failed: {error_msg}")

        logger.info("MySQL restore completed successfully.")
