"""Abstract base class for database connectors."""

from abc import ABC, abstractmethod


class BaseConnector(ABC):
    """Base interface that every database connector must implement."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Test the database connection. Returns True on success."""
        ...

    @abstractmethod
    def backup(self, dest_path: str, tables: list[str] | None = None) -> str:
        """Create a backup of the database.

        Args:
            dest_path: Directory where the backup file will be saved.
            tables: Optional list of specific tables/collections to back up.

        Returns:
            The path to the generated backup file.
        """
        ...

    @abstractmethod
    def restore(self, backup_file: str, tables: list[str] | None = None) -> None:
        """Restore a database from a backup file.

        Args:
            backup_file: Path to the backup file.
            tables: Optional list of specific tables/collections to restore.
        """
        ...
