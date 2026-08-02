import logging
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from sparkstagelapse.display import display

logger = logging.getLogger(__name__)

# --- Users data (same as your example) ---
users_data = [
    {
        "user_id": 1001,
        "name": "Alice Martin",
        "country": "FR",
        "city": "Paris",
        "age": 31,
        "signup_date": datetime(2025, 3, 14, 9, 30),
        "is_active": True,
        "plan": "pro",
        "orders_count": 14,
        "total_spent": 482.75,
        "tags": ["etl", "spark", "databricks"],
        "preferences": {"theme": "dark", "lang": "fr"},
    },
    {
        "user_id": 1002,
        "name": "Ben Carter",
        "country": "US",
        "city": "New York",
        "age": 27,
        "signup_date": datetime(2025, 6, 2, 15, 45),
        "is_active": False,
        "plan": "free",
        "orders_count": 2,
        "total_spent": 19.99,
        "tags": ["analytics", "python"],
        "preferences": {"theme": "light", "lang": "en"},
    },
    {
        "user_id": 1003,
        "name": "Chloé Bernard",
        "country": "FR",
        "city": "Lyon",
        "age": None,
        "signup_date": datetime(2025, 1, 22, 8, 10),
        "is_active": True,
        "plan": "enterprise",
        "orders_count": 42,
        "total_spent": 3240.10,
        "tags": ["sql", "governance", "m365"],
        "preferences": {"theme": "dark", "lang": "fr"},
    },
    {
        "user_id": 1004,
        "name": "Diego Silva",
        "country": "BR",
        "city": "São Paulo",
        "age": 39,
        "signup_date": datetime(2024, 11, 18, 11, 5),
        "is_active": True,
        "plan": "pro",
        "orders_count": 8,
        "total_spent": 210.50,
        "tags": [],
        "preferences": {"theme": "dark", "lang": "pt"},
    },
]

# --- Orders data (to join with users) ---
orders_data = [
    {"order_id": 1, "user_id": 1001, "amount": 120.50, "status": "completed"},
    {"order_id": 2, "user_id": 1001, "amount": 55.00, "status": "completed"},
    {"order_id": 3, "user_id": 1002, "amount": 19.99, "status": "refunded"},
    {"order_id": 4, "user_id": 1003, "amount": 890.00, "status": "completed"},
    {"order_id": 5, "user_id": 1003, "amount": 1200.00, "status": "completed"},
    {"order_id": 6, "user_id": 1005, "amount": 300.00, "status": "pending"},  # no matching user
]

if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    logger.info("Running Spark join example")

    spark = (
        SparkSession.builder
        .appName("sparkstagelapse-join-demo")
        .getOrCreate()
    )

    # Create DataFrames
    users_df = spark.createDataFrame(users_data)
    orders_df = spark.createDataFrame(orders_data)

    display(users_df, title="Users (raw)", plan=False)
    display(orders_df, title="Orders (raw)", plan=False)

    # Inner join: only users with at least one order
    users_orders_inner = (
        users_df
        .alias("u")
        .join(
            orders_df.alias("o"),
            on="user_id",
            how="inner",
        )
        .select(
            F.col("u.user_id"),
            F.col("u.name"),
            F.col("u.country"),
            F.col("o.order_id"),
            F.col("o.amount"),
            F.col("o.status"),
        )
    )

    display(users_orders_inner, title="Users ⨝ Orders (inner join)", plan=False)

    # Left join: all users, with order info where available
    users_orders_left = (
        users_df
        .alias("u")
        .join(
            orders_df.alias("o"),
            on="user_id",
            how="left",
        )
        .select(
            F.col("u.user_id"),
            F.col("u.name"),
            F.col("u.country"),
            F.col("o.order_id"),
            F.col("o.amount"),
            F.col("o.status"),
        )
    )

    display(users_orders_left, title="Users ⨝ Orders (left join)", plan=False)

    # Aggregation after join: total order amount per user
    user_order_agg = (
        users_df
        .alias("u")
        .join(
            orders_df.alias("o"),
            on="user_id",
            how="left",
        )
        .groupBy("u.user_id", "u.name", "u.country")
        .agg(
            F.count("o.order_id").alias("num_orders"),
            F.sum("o.amount").alias("total_order_amount"),
            F.avg("o.amount").alias("avg_order_amount"),
        )
        .orderBy("u.user_id")
    )

    display(user_order_agg, title="User order aggregates (after join)", plan=False)

    logger.info("DONE")