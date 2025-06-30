import mysql.connector
from mysql.connector import Error
import os


def create_agent_user(
    database_name: str,
    database_host: str,
    database_port: int,
    database_root_user: str,
    database_root_password: str,
    agent_user: str,
    agent_password: str,
):
    """
    Creates a read-only MySQL user for the AI agent with limited permissions.
    """

    # Database connection parameters (admin credentials)
    config = {
        "host": database_host,
        "user": database_root_user,
        "password": database_root_password,
        "port": database_port,
        "database": database_name,
    }

    try:
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()

        # Drop user if exists (for clean setup)
        cursor.execute(f"DROP USER IF EXISTS '{agent_user}'@'%'")
        cursor.execute(f"DROP USER IF EXISTS '{agent_user}'@'localhost'")

        # Create the agent user
        cursor.execute(
            f"CREATE USER '{agent_user}'@'%' IDENTIFIED BY '{agent_password}'"
        )
        cursor.execute(
            f"CREATE USER '{agent_user}'@'localhost' IDENTIFIED BY '{agent_password}'"
        )

        # Grant only SELECT permissions on the database
        cursor.execute(f"GRANT SELECT ON {database_name}.* TO '{agent_user}'@'%'")
        cursor.execute(
            f"GRANT SELECT ON {database_name}.* TO '{agent_user}'@'localhost'"
        )

        # Flush privileges to ensure changes take effect
        cursor.execute("FLUSH PRIVILEGES")

        connection.commit()
        print(
            f"Agent user '{agent_user}' created successfully with read-only permissions"
        )

        # Verify user creation
        cursor.execute(
            "SELECT User, Host FROM mysql.user WHERE User = %s", (agent_user,)
        )
        users = cursor.fetchall()
        print(f"Created users: {users}")

        # Verify permissions
        cursor.execute("SHOW GRANTS FOR %s@'%'", (agent_user,))
        grants = cursor.fetchall()
        print(f"Granted permissions: {grants}")

    except Error as e:
        print(f"Error creating agent user: {e}")
        if connection:
            connection.rollback()
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed")


def test_agent_user_connection():
    """Test that the agent user can connect and has proper permissions"""

    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_AGENT_USER", "ai_agent"),
        "password": os.getenv("DB_AGENT_PASSWORD", "agent_readonly_pass"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "database": os.getenv("DB_NAME", "ecommerce_db"),
    }

    try:
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()

        # Test SELECT permission
        cursor.execute("SELECT COUNT(*) FROM customers")
        result = cursor.fetchone()
        print(f"Agent user can read data - Customer count: {result[0]}")

        # Test that user cannot write (should fail)
        try:
            cursor.execute(
                "INSERT INTO customers (first_name, last_name, email) VALUES ('Test', 'User', 'test@test.com')"
            )
            print("WARNING: Agent user has write permissions (this should not happen)")
        except Error as e:
            print(f"Good: Agent user properly restricted from writing - {e.msg}")

        print("Agent user setup verification completed successfully")

    except Error as e:
        print(f"Error testing agent user: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


if __name__ == "__main__":
    create_agent_user()
    test_agent_user_connection()
