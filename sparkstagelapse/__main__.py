from datetime import datetime

import pyspark.sql.functions as F
from pyspark.sql import SparkSession
from sparkstagelapse.display import display
import logging
logger=logging.getLogger(__name__)

data = [
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

if __name__=="__main__":
    logger.info('Running basic spark command')
    spark = SparkSession.builder.appName("sparkstagelapse-demo").getOrCreate()
    df = spark.createDataFrame(data)
    display(df,title="Raw data",mode="web")
    # display(df.select(F.col("tags")),title="After Selection")
    logger.info('DONE')


