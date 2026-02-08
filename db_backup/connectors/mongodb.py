"""MongoDB connector using mongodump / mongorestore CLI tools."""

import logging
import os
import shutil
import subprocess
from datetime import datetime

from db_backup.connectors import BaseConnector

logger = logging.getLogger("db_backup")


class MongoDBConnector(BaseConnector):
    """Connector for MongoDB databases."""

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

    def _uri(self) -> str:
        """Build a MongoDB connection URI."""
        if self.user and self.password:
            return f"mongodb://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?authSource=admin"
        return f"mongodb://{self.host}:{self.port}/{self.database}"

    # ------------------------------------------------------------------ #
    #  Connection test
    # ------------------------------------------------------------------ #
    def test_connection(self) -> bool:
        try:
            from pymongo import MongoClient

            client = MongoClient(self._uri(), serverSelectionTimeoutMS=10000)
            client.server_info()        # force connection
            client.close()
            logger.info("MongoDB connection successful (%s:%s/%s)", self.host, self.port, self.database)
            return True
        except Exception as exc:
            logger.error("MongoDB connection failed: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    #  Backup
    # ------------------------------------------------------------------ #
    def backup(self, dest_path: str, tables: list[str] | None = None) -> str:
        os.makedirs(dest_path, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_dir = os.path.join(dest_path, f"mongo_{self.database}_{timestamp}")

        cmd = [
            "mongodump",
            f"--uri={self._uri()}",
            f"--out={dump_dir}",
        ]

        if tables:
            # mongodump supports --collection for a single collection
            # For multiple, run once per collection
            for collection in tables:
                col_cmd = cmd + [f"--collection={collection}"]
                logger.info("Dumping collection '%s' ...", collection)
                result = subprocess.run(col_cmd, stderr=subprocess.PIPE, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"mongodump failed for collection '{collection}': {result.stderr.strip()}")
        else:
            logger.info("Running mongodump for database '%s' ...", self.database)
            result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"mongodump failed: {result.stderr.strip()}")

        # Archive the dump directory into a tar file
        archive_path = dump_dir + ".tar"
        logger.info("Archiving dump directory ...")
        shutil.make_archive(dump_dir, "tar", root_dir=dest_path, base_dir=os.path.basename(dump_dir))
        shutil.rmtree(dump_dir, ignore_errors=True)

        logger.info("MongoDB backup created: %s", archive_path)
        return archive_path

    # ------------------------------------------------------------------ #
    #  Restore
    # ------------------------------------------------------------------ #
    def restore(self, backup_file: str, tables: list[str] | None = None) -> None:
        if not os.path.isfile(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        # Extract the archive first
        restore_dir = backup_file.replace(".tar", "_restore")
        os.makedirs(restore_dir, exist_ok=True)
        shutil.unpack_archive(backup_file, restore_dir, "tar")

        cmd = [
            "mongorestore",
            f"--uri={self._uri()}",
            "--drop",
        ]

        if tables:
            for collection in tables:
                col_cmd = cmd + [f"--collection={collection}", f"--nsInclude={self.database}.{collection}"]
                col_cmd.append(restore_dir)
                result = subprocess.run(col_cmd, stderr=subprocess.PIPE, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"mongorestore failed for '{collection}': {result.stderr.strip()}")
        else:
            cmd.append(restore_dir)
            logger.info("Restoring MongoDB database '%s' from %s ...", self.database, backup_file)
            result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"mongorestore failed: {result.stderr.strip()}")

        # Clean up extracted files
        shutil.rmtree(restore_dir, ignore_errors=True)
        logger.info("MongoDB restore completed successfully.")
