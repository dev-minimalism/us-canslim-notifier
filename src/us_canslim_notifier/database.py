"""Database connection with SSH tunnel support using paramiko."""

import atexit
import socket
import threading
from contextlib import contextmanager
from typing import Optional

import paramiko
import psycopg2
from psycopg2.extras import RealDictCursor

from .settings import settings


class SSHTunnel:
    """SSH tunnel manager using paramiko."""

    def __init__(self):
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.transport: Optional[paramiko.Transport] = None
        self.local_port: Optional[int] = None
        self._channel: Optional[paramiko.Channel] = None
        self._forward_server: Optional[socket.socket] = None
        self._forward_thread: Optional[threading.Thread] = None
        self._running = False

    def _find_free_port(self) -> int:
        """Find a free local port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def connect(self) -> int:
        """
        Establish SSH tunnel and return local port.

        Returns:
            Local port number for database connection
        """
        if self.local_port is not None:
            return self.local_port

        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.ssh_client.connect(
                hostname=settings.SSH_HOST,
                port=settings.SSH_PORT,
                username=settings.SSH_USER,
                key_filename=settings.SSH_KEY_PATH,
                timeout=30,
            )
            print(f"  SSH connected to {settings.SSH_HOST}")

            self.transport = self.ssh_client.get_transport()
            self.local_port = self._find_free_port()

            # Start port forwarding in background thread
            self._running = True
            self._forward_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._forward_server.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            self._forward_server.bind(("127.0.0.1", self.local_port))
            self._forward_server.listen(5)
            self._forward_server.settimeout(1.0)

            self._forward_thread = threading.Thread(
                target=self._forward_loop, daemon=True
            )
            self._forward_thread.start()

            print(f"  SSH tunnel: localhost:{self.local_port} -> {settings.DB_HOST}:{settings.DB_PORT}")
            return self.local_port

        except Exception as e:
            self.close()
            raise ConnectionError(f"SSH tunnel failed: {e}")

    def _forward_loop(self):
        """Handle incoming connections and forward through SSH tunnel."""
        while self._running:
            try:
                client_socket, _ = self._forward_server.accept()
                # Create channel to remote database
                channel = self.transport.open_channel(
                    "direct-tcpip",
                    (settings.DB_HOST, settings.DB_PORT),
                    client_socket.getpeername(),
                )
                if channel is None:
                    client_socket.close()
                    continue

                # Start bidirectional forwarding
                threading.Thread(
                    target=self._forward_data,
                    args=(client_socket, channel),
                    daemon=True,
                ).start()

            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    continue
                break

    def _forward_data(self, client_socket: socket.socket, channel: paramiko.Channel):
        """Forward data between local socket and SSH channel."""
        try:
            while True:
                # Check both directions
                r_ready = []
                if client_socket.fileno() != -1:
                    client_socket.setblocking(False)
                    try:
                        data = client_socket.recv(4096)
                        if data:
                            channel.send(data)
                        else:
                            break
                    except BlockingIOError:
                        pass
                    except Exception:
                        break
                    finally:
                        client_socket.setblocking(True)

                if channel.recv_ready():
                    data = channel.recv(4096)
                    if data:
                        client_socket.send(data)
                    else:
                        break

                # Small sleep to prevent busy loop
                import time
                time.sleep(0.001)

        except Exception:
            pass
        finally:
            try:
                channel.close()
            except Exception:
                pass
            try:
                client_socket.close()
            except Exception:
                pass

    def close(self):
        """Close SSH tunnel."""
        self._running = False

        if self._forward_server:
            try:
                self._forward_server.close()
            except Exception:
                pass
            self._forward_server = None

        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception:
                pass
            self.ssh_client = None

        self.transport = None
        self.local_port = None
        print("  SSH tunnel closed")


class DatabaseManager:
    """PostgreSQL database manager with SSH tunnel support."""

    def __init__(self):
        self.tunnel: Optional[SSHTunnel] = None
        self._connection: Optional[psycopg2.extensions.connection] = None

    def connect(self) -> bool:
        """
        Establish database connection through SSH tunnel.

        Returns:
            True if connection successful
        """
        if not settings.is_db_configured():
            print("Database settings not configured")
            return False

        try:
            # Establish SSH tunnel
            self.tunnel = SSHTunnel()
            local_port = self.tunnel.connect()

            # Connect to PostgreSQL through tunnel
            self._connection = psycopg2.connect(
                host="127.0.0.1",
                port=local_port,
                database=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                connect_timeout=10,
            )
            self._connection.autocommit = False
            print(f"  Connected to database: {settings.DB_NAME}")
            return True

        except Exception as e:
            print(f"Database connection failed: {e}")
            self.close()
            return False

    def close(self):
        """Close database connection and SSH tunnel."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

        if self.tunnel:
            self.tunnel.close()
            self.tunnel = None

    @contextmanager
    def get_cursor(self, dict_cursor: bool = True):
        """
        Get database cursor as context manager.

        Args:
            dict_cursor: Use RealDictCursor for dict-like row access

        Yields:
            Database cursor
        """
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor_factory = RealDictCursor if dict_cursor else None
        cursor = self._connection.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cursor.close()

    def _check_connection(self) -> bool:
        """Check if connection is alive, attempt reconnect if not."""
        if self._connection is None:
            return False

        try:
            # Simple query to check connection
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            print("  ⚠️  DB connection lost, attempting reconnect...")
            self.close()
            return self.connect()

    def execute(self, query: str, params: tuple = None) -> list:
        """
        Execute query and return results.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of rows as dicts
        """
        if not self._check_connection():
            return []

        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:
                return cursor.fetchall()
            return []

    def execute_one(self, query: str, params: tuple = None) -> Optional[dict]:
        """
        Execute query and return single result.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Single row as dict or None
        """
        if not self._check_connection():
            return None

        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:
                return cursor.fetchone()
            return None

    def init_schema(self):
        """Initialize database schema (create tables if not exist)."""
        schema_sql = """
        -- Positions table for paper trading
        CREATE TABLE IF NOT EXISTS positions (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            entry_price DECIMAL(12, 4) NOT NULL,
            entry_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            exit_price DECIMAL(12, 4),
            exit_date TIMESTAMP,
            pattern VARCHAR(100),
            stop_loss DECIMAL(12, 4),
            take_profit DECIMAL(12, 4),
            signal_data JSONB,
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            exit_reason VARCHAR(100),
            profit_pct DECIMAL(8, 4),
            holding_days INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Index for faster queries
        CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
        CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker);
        CREATE INDEX IF NOT EXISTS idx_positions_entry_date ON positions(entry_date);

        -- Trade history table for closed positions summary
        CREATE TABLE IF NOT EXISTS trade_history (
            id SERIAL PRIMARY KEY,
            position_id INTEGER REFERENCES positions(id),
            ticker VARCHAR(20) NOT NULL,
            entry_price DECIMAL(12, 4) NOT NULL,
            exit_price DECIMAL(12, 4) NOT NULL,
            entry_date TIMESTAMP NOT NULL,
            exit_date TIMESTAMP NOT NULL,
            profit_pct DECIMAL(8, 4) NOT NULL,
            holding_days INTEGER NOT NULL,
            exit_reason VARCHAR(100),
            pattern VARCHAR(100),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_trade_history_ticker ON trade_history(ticker);
        CREATE INDEX IF NOT EXISTS idx_trade_history_exit_date ON trade_history(exit_date);
        """

        with self.get_cursor() as cursor:
            cursor.execute(schema_sql)
        print("  Database schema initialized")


# Global database manager instance
db_manager: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Get or create database manager instance."""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager


def init_db() -> bool:
    """Initialize database connection and schema."""
    db = get_db()
    if db.connect():
        db.init_schema()
        # Register cleanup on exit
        atexit.register(db.close)
        return True
    return False


def close_db():
    """Close database connection."""
    global db_manager
    if db_manager:
        db_manager.close()
        db_manager = None
