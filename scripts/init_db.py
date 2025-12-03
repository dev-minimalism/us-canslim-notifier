#!/usr/bin/env python3
"""Initialize database on remote PostgreSQL server via SSH tunnel."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paramiko
from dotenv import load_dotenv

load_dotenv()


def create_database():
    """Create database on remote server via SSH."""
    ssh_host = os.getenv("SSH_HOST")
    ssh_port = int(os.getenv("SSH_PORT", "22"))
    ssh_user = os.getenv("SSH_USER")
    ssh_key_path = os.path.expanduser(os.getenv("SSH_KEY_PATH", "~/.ssh/id_rsa"))
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")

    print(f"Connecting to {ssh_host}...")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=ssh_host,
            port=ssh_port,
            username=ssh_user,
            key_filename=ssh_key_path,
        )
        print("SSH connected!")

        # Check if database exists
        check_cmd = f"sudo -u postgres psql -lqt | cut -d \\| -f 1 | grep -qw {db_name}"
        stdin, stdout, stderr = ssh.exec_command(check_cmd)
        exit_status = stdout.channel.recv_exit_status()

        if exit_status == 0:
            print(f"Database '{db_name}' already exists.")
        else:
            # Create database using createdb command (if user has permission)
            # Or connect to postgres database and create
            print(f"Creating database '{db_name}'...")
            create_cmd = f'createdb "{db_name}"'
            stdin, stdout, stderr = ssh.exec_command(create_cmd)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status == 0:
                print(f"Database '{db_name}' created successfully!")
            else:
                error = stderr.read().decode()
                if "already exists" in error:
                    print(f"Database '{db_name}' already exists.")
                else:
                    print(f"Error creating database: {error}")
                    print("\nPlease run manually on the server:")
                    print(f"  sudo -u postgres createdb {db_name} -O {db_user}")
                    return False

        print("Done!")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        ssh.close()


if __name__ == "__main__":
    success = create_database()
    sys.exit(0 if success else 1)
