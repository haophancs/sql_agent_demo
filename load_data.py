import pandas as pd
from agents import db_url
from agno.utils.log import logger
from sqlalchemy import create_engine
import os

# List of files and their corresponding table names
files_to_tables = {
    "data/dim_customer.csv": "DIM_CUSTOMER",
    "data/dim_date.csv": "DIM_DATE",
    "data/dim_employee.csv": "DIM_EMPLOYEE",
    "data/dim_product.csv": "DIM_PRODUCT",
    "data/dim_promotion.csv": "DIM_PROMOTION",
    "data/dim_store.csv": "DIM_STORE",
    "data/dim_supplier.csv": "DIM_SUPPLIER",
    "data/fact_employee_performance.csv": "FACT_EMPLOYEE_PERFORMANCE",
    "data/fact_inventory.csv": "FACT_INVENTORY",
    "data/fact_purchase_orders.csv": "FACT_PURCHASE_ORDERS",
    "data/fact_sales.csv": "FACT_SALES"
}

def load_retail_data():
    """Load retail inventory data into the database"""

    logger.info("Loading retail database.")
    engine = create_engine(db_url)

    # Load each CSV file into the corresponding PostgreSQL table
    for file_path, table_name in files_to_tables.items():
        if not os.path.exists(file_path):
            logger.warning(f"File {file_path} not found. Skipping.")
            continue
            
        logger.info(f"Loading {file_path} into {table_name} table.")
        
        # Read the CSV file directly
        df = pd.read_csv(file_path)
        
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        logger.info(f"{file_path} loaded into {table_name} table.")

    logger.info("Retail database loaded.")


if __name__ == "__main__":
    load_retail_data()
