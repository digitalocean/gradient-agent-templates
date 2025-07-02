"""
Creates a database with some dummy info for easy testing
"""

import mysql.connector
from mysql.connector import Error
import argparse


def create_mock_database_and_tables(
    db_host: str,
    db_user: str,
    db_password: str,
    db_port: int,
    database_name: str = "ecommerce_db",
):
    """
    Creates a MySQL database with sample e-commerce tables and populates them with data.
    Tables: customers, products, categories, orders, order_items
    """

    # Database connection parameters
    config = {
        "host": db_host,
        "user": db_user,
        "password": db_password,
        "port": db_port,
    }

    try:
        # Connect without specifying database to create it
        print("Connecting")
        connection = mysql.connector.connect(**config)
        print("Conn")
        cursor = connection.cursor()

        print("Connected!")

        # Create database
        cursor.execute(f"DROP DATABASE IF EXISTS {database_name}")
        cursor.execute(f"CREATE DATABASE {database_name}")
        cursor.execute(f"USE {database_name}")

        print(f"Database '{database_name}' created successfully")

        # Create categories table
        cursor.execute("""
            CREATE TABLE categories (
                category_id INT PRIMARY KEY AUTO_INCREMENT,
                category_name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create customers table
        cursor.execute("""
            CREATE TABLE customers (
                customer_id INT PRIMARY KEY AUTO_INCREMENT,
                first_name VARCHAR(50) NOT NULL,
                last_name VARCHAR(50) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                phone VARCHAR(20),
                date_of_birth DATE,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                total_orders INT DEFAULT 0,
                lifetime_value DECIMAL(10,2) DEFAULT 0.00
            )
        """)

        # Create products table
        cursor.execute("""
            CREATE TABLE products (
                product_id INT PRIMARY KEY AUTO_INCREMENT,
                product_name VARCHAR(200) NOT NULL,
                category_id INT,
                price DECIMAL(10,2) NOT NULL,
                stock_quantity INT DEFAULT 0,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(category_id)
            )
        """)

        # Create orders table
        cursor.execute("""
            CREATE TABLE orders (
                order_id INT PRIMARY KEY AUTO_INCREMENT,
                customer_id INT NOT NULL,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount DECIMAL(10,2) NOT NULL,
                status ENUM('pending', 'processing', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
                shipping_address TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        # Create order_items table
        cursor.execute("""
            CREATE TABLE order_items (
                order_item_id INT PRIMARY KEY AUTO_INCREMENT,
                order_id INT NOT NULL,
                product_id INT NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL,
                total_price DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """)

        print("Tables created successfully")

        # Populate with sample data
        populate_sample_data(cursor)

        connection.commit()
        print("Sample data inserted successfully")

    except Error as e:
        print(f"Error: {e}")
        if connection:
            connection.rollback()
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed")


def populate_sample_data(cursor):
    """Populate tables with sample data"""

    # Insert categories
    categories = [
        ("Electronics", "Electronic devices and gadgets"),
        ("Clothing", "Fashion and apparel"),
        ("Books", "Books and literature"),
        ("Home & Garden", "Home improvement and gardening"),
        ("Sports", "Sports equipment and accessories"),
    ]

    cursor.executemany(
        """
        INSERT INTO categories (category_name, description) 
        VALUES (%s, %s)
    """,
        categories,
    )

    # Insert customers
    customers = [
        ("John", "Doe", "john.doe@email.com", "555-0101", "1985-03-15"),
        ("Jane", "Smith", "jane.smith@email.com", "555-0102", "1990-07-22"),
        ("Michael", "Johnson", "michael.j@email.com", "555-0103", "1982-11-08"),
        ("Emily", "Brown", "emily.brown@email.com", "555-0104", "1988-01-30"),
        ("David", "Wilson", "david.wilson@email.com", "555-0105", "1975-09-12"),
        ("Sarah", "Davis", "sarah.davis@email.com", "555-0106", "1992-04-18"),
        ("Robert", "Miller", "robert.miller@email.com", "555-0107", "1978-12-05"),
        ("Lisa", "Anderson", "lisa.anderson@email.com", "555-0108", "1986-06-25"),
    ]

    cursor.executemany(
        """
        INSERT INTO customers (first_name, last_name, email, phone, date_of_birth) 
        VALUES (%s, %s, %s, %s, %s)
    """,
        customers,
    )

    # Insert products
    products = [
        ("iPhone 15", 1, 999.99, 50, "Latest Apple smartphone"),
        ("Samsung Galaxy S24", 1, 899.99, 30, "Android flagship phone"),
        ("MacBook Pro", 1, 1999.99, 15, "Professional laptop"),
        ("Wireless Headphones", 1, 199.99, 100, "Noise-cancelling headphones"),
        ("Blue Jeans", 2, 79.99, 200, "Classic denim jeans"),
        ("Cotton T-Shirt", 2, 24.99, 300, "Comfortable cotton tee"),
        ("Winter Jacket", 2, 149.99, 75, "Warm winter outerwear"),
        ("Python Programming", 3, 45.99, 25, "Learn Python programming"),
        ("Data Science Handbook", 3, 59.99, 20, "Complete guide to data science"),
        ("Garden Tools Set", 4, 129.99, 40, "Complete gardening toolkit"),
        ("Indoor Plant Pot", 4, 19.99, 150, "Decorative plant container"),
        ("Tennis Racket", 5, 89.99, 60, "Professional tennis racket"),
        ("Running Shoes", 5, 119.99, 80, "Comfortable running footwear"),
    ]

    cursor.executemany(
        """
        INSERT INTO products (product_name, category_id, price, stock_quantity, description) 
        VALUES (%s, %s, %s, %s, %s)
    """,
        products,
    )

    # Insert orders
    orders = [
        (1, "2024-01-15 10:30:00", 1199.98, "delivered", "123 Main St, City, State"),
        (2, "2024-01-20 14:15:00", 104.98, "delivered", "456 Oak Ave, City, State"),
        (3, "2024-02-01 09:45:00", 2199.98, "shipped", "789 Pine Rd, City, State"),
        (4, "2024-02-05 16:20:00", 269.97, "processing", "321 Elm St, City, State"),
        (5, "2024-02-10 11:10:00", 149.98, "pending", "654 Maple Dr, City, State"),
        (1, "2024-02-15 13:30:00", 45.99, "delivered", "123 Main St, City, State"),
        (6, "2024-02-20 15:45:00", 89.99, "shipped", "987 Cedar Ln, City, State"),
    ]

    cursor.executemany(
        """
        INSERT INTO orders (customer_id, order_date, total_amount, status, shipping_address) 
        VALUES (%s, %s, %s, %s, %s)
    """,
        orders,
    )

    # Insert order items
    order_items = [
        (1, 1, 1, 999.99, 999.99),
        (1, 4, 1, 199.99, 199.99),
        (2, 5, 1, 79.99, 79.99),
        (2, 6, 1, 24.99, 24.99),
        (3, 3, 1, 1999.99, 1999.99),
        (3, 4, 1, 199.99, 199.99),
        (4, 7, 1, 149.99, 149.99),
        (4, 4, 1, 199.99, 199.99),
        (4, 6, 1, 24.99, 24.99),
        (5, 7, 1, 149.99, 149.99),
        (6, 8, 1, 45.99, 45.99),
        (7, 12, 1, 89.99, 89.99),
    ]

    cursor.executemany(
        """
        INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price) 
        VALUES (%s, %s, %s, %s, %s)
    """,
        order_items,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Create mock database and tables")

    parser.add_argument("--db-host", required=True, help="Database host")
    parser.add_argument("--db-user", required=True, help="Database user")
    parser.add_argument("--db-password", required=True, help="Database password")
    parser.add_argument("--db-port", type=int, required=True, help="Database port")
    parser.add_argument(
        "--database-name",
        default="ecommerce_db",
        help="Database name (default: ecommerce_db)",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Create the mock database and tables
    create_mock_database_and_tables(
        db_host=args.db_host,
        db_user=args.db_user,
        db_password=args.db_password,
        db_port=args.db_port,
        database_name=args.database_name,
    )

    print(f"Mock database '{args.database_name}' created successfully!")


if __name__ == "__main__":
    main()
