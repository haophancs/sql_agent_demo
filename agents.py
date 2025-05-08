"""💎 Retail Analytics SQL Agent - Your AI Retail Data Analyst!

This advanced example shows how to build a sophisticated text-to-SQL system that
leverages Reasoning Agents to provide deep insights into retail and inventory data.

Example queries to try:
- "Who are the top 5 customers by total purchase amount?"
- "Compare sales performance between different store locations"
- "Show me the inventory trends for our top-selling products"
- "Which products have the highest profit margins?"
- "What are our current stockout items across all stores?"
- "Show me the sales performance by promotion type"

Examples with table joins:
- "How do employee performance metrics correlate with sales figures?"
- "Compare inventory levels against sales volume for top products"
- "Show me customer purchase patterns across different product categories"
- "Which suppliers have the most stockouts in the last quarter?"
- "Show me the relationship between promotion campaigns and product profitability"
View the README for instructions on how to run the application.
"""

import json
from pathlib import Path
from textwrap import dedent
from typing import Optional

from agno.agent import Agent
from agno.embedder.openai import OpenAIEmbedder
from agno.knowledge.combined import CombinedKnowledgeBase
from agno.knowledge.json import JSONKnowledgeBase
from agno.knowledge.text import TextKnowledgeBase
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.models.groq import Groq
from agno.models.openai import OpenAIChat
from agno.storage.agent.postgres import PostgresAgentStorage
from agno.tools.file import FileTools
from agno.tools.sql import SQLTools
from agno.vectordb.pgvector import PgVector

# ************* Database Connection *************
db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"
# *******************************

# ************* Paths *************
cwd = Path(__file__).parent
knowledge_dir = cwd.joinpath("knowledge")
output_dir = cwd.joinpath("output")

# Create the output directory if it does not exist
output_dir.mkdir(parents=True, exist_ok=True)
# *******************************

# ************* Storage & Knowledge *************
agent_storage = PostgresAgentStorage(
    db_url=db_url,
    # Store agent sessions in the ai.sql_agent_sessions table
    table_name="sql_agent_sessions",
    schema="ai",
)
agent_knowledge = CombinedKnowledgeBase(
    sources=[
        # Reads text files, SQL files, and markdown files
        TextKnowledgeBase(
            path=knowledge_dir,
            formats=[".txt", ".sql", ".md"],
        ),
        # Reads JSON files
        JSONKnowledgeBase(path=knowledge_dir),
    ],
    # Store agent knowledge in the ai.sql_agent_knowledge table
    vector_db=PgVector(
        db_url=db_url,
        table_name="sql_agent_knowledge",
        schema="ai",
        # Use OpenAI embeddings
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    # 5 references are added to the prompt
    num_documents=5,
)
# *******************************

# ************* Semantic Model *************
# The semantic model helps the agent identify the tables and columns to use
# This is sent in the system prompt, the agent then uses the `search_knowledge_base` tool to get table metadata, rules and sample queries
# This is very much how data analysts and data scientists work:
#  - We start with a set of tables and columns that we know are relevant to the task
#  - We then use the `search_knowledge_base` tool to get more information about the tables and columns
#  - We then use the `search_knowledge_base` tool to get sample queries for the tables and columns
#  - We then use the `describe_table` tool to get more information about the tables and columns
semantic_model = {
    "tables": [
        {
            "table_name": "DIM_CUSTOMER",
            "table_description": "Customer dimension table for loyalty analysis with customer details and segments.",
            "Use Case": "Use this table for customer profiling, loyalty analysis, and demographic studies.",
            "relationships": [
                {
                    "related_table": "FACT_SALES",
                    "relationship_type": "one-to-many",
                    "join_columns": {"customer_id": "customer_id"},
                    "description": "One customer makes many sales"
                }
            ]
        },
        {
            "table_name": "DIM_DATE",
            "table_description": "Date dimension table with calendar attributes for time-based analysis.",
            "Use Case": "Use this table for temporal analysis, seasonality studies, and periodic reporting.",
            "relationships": [
                {
                    "related_table": "FACT_SALES",
                    "relationship_type": "one-to-many",
                    "join_columns": {"date_id": "date_id"},
                    "description": "One date has many sales"
                },
                {
                    "related_table": "FACT_INVENTORY",
                    "relationship_type": "one-to-many",
                    "join_columns": {"date_id": "date_id"},
                    "description": "One date has many inventory records"
                },
                {
                    "related_table": "FACT_PURCHASE_ORDERS",
                    "relationship_type": "one-to-many",
                    "join_columns": {"date_id": "date_id"},
                    "description": "One date has many purchase orders"
                },
                {
                    "related_table": "FACT_EMPLOYEE_PERFORMANCE",
                    "relationship_type": "one-to-many",
                    "join_columns": {"date_id": "date_id"},
                    "description": "One date has many employee performance records"
                }
            ]
        },
        {
            "table_name": "DIM_EMPLOYEE",
            "table_description": "Employee dimension table with personnel details and roles.",
            "Use Case": "Use this table for workforce analysis, performance evaluation, and organizational studies.",
            "relationships": [
                {
                    "related_table": "FACT_SALES",
                    "relationship_type": "one-to-many",
                    "join_columns": {"employee_id": "employee_id"},
                    "description": "One employee processes many sales"
                },
                {
                    "related_table": "FACT_EMPLOYEE_PERFORMANCE",
                    "relationship_type": "one-to-many",
                    "join_columns": {"employee_id": "employee_id"},
                    "description": "One employee has many performance records"
                }
            ]
        },
        {
            "table_name": "DIM_PRODUCT",
            "table_description": "Product dimension table with catalog information, pricing, and suppliers.",
            "Use Case": "Use this table for product analysis, category performance, and pricing strategies.",
            "relationships": [
                {
                    "related_table": "FACT_SALES",
                    "relationship_type": "one-to-many",
                    "join_columns": {"product_id": "product_id"},
                    "description": "One product included in many sales"
                },
                {
                    "related_table": "FACT_INVENTORY",
                    "relationship_type": "one-to-many",
                    "join_columns": {"product_id": "product_id"},
                    "description": "One product has many inventory records"
                },
                {
                    "related_table": "FACT_PURCHASE_ORDERS",
                    "relationship_type": "one-to-many",
                    "join_columns": {"product_id": "product_id"},
                    "description": "One product ordered in many purchase orders"
                },
                {
                    "related_table": "DIM_SUPPLIER",
                    "relationship_type": "many-to-one",
                    "join_columns": {"supplier_id": "supplier_id"},
                    "description": "Many products provided by one supplier"
                }
            ]
        },
        {
            "table_name": "DIM_PROMOTION",
            "table_description": "Promotion dimension table with campaign details and discounts.",
            "Use Case": "Use this table for promotional effectiveness, campaign analysis, and discount evaluation.",
            "relationships": [
                {
                    "related_table": "FACT_SALES",
                    "relationship_type": "one-to-many",
                    "join_columns": {"promotion_id": "promotion_id"},
                    "description": "One promotion applied to many sales"
                }
            ]
        },
        {
            "table_name": "DIM_STORE",
            "table_description": "Store dimension table with location details and attributes.",
            "Use Case": "Use this table for location analysis, store performance, and geographical studies.",
            "relationships": [
                {
                    "related_table": "FACT_SALES",
                    "relationship_type": "one-to-many",
                    "join_columns": {"store_id": "store_id"},
                    "description": "One store generates many sales"
                },
                {
                    "related_table": "FACT_INVENTORY",
                    "relationship_type": "one-to-many",
                    "join_columns": {"store_id": "store_id"},
                    "description": "One store maintains many inventory records"
                },
                {
                    "related_table": "FACT_EMPLOYEE_PERFORMANCE",
                    "relationship_type": "one-to-many",
                    "join_columns": {"store_id": "store_id"},
                    "description": "One store has many employee performance records"
                }
            ]
        },
        {
            "table_name": "DIM_SUPPLIER",
            "table_description": "Supplier dimension table with vendor details and terms.",
            "Use Case": "Use this table for supplier performance, vendor relations, and procurement analysis.",
            "relationships": [
                {
                    "related_table": "DIM_PRODUCT",
                    "relationship_type": "one-to-many",
                    "join_columns": {"supplier_id": "supplier_id"},
                    "description": "One supplier provides many products"
                },
                {
                    "related_table": "FACT_PURCHASE_ORDERS",
                    "relationship_type": "one-to-many",
                    "join_columns": {"supplier_id": "supplier_id"},
                    "description": "One supplier receives many purchase orders"
                }
            ]
        },
        {
            "table_name": "FACT_EMPLOYEE_PERFORMANCE",
            "table_description": "Employee performance fact table with metrics and KPIs.",
            "Use Case": "Use this table for workforce productivity analysis, performance evaluation, and HR analytics.",
            "relationships": [
                {
                    "related_table": "DIM_DATE",
                    "relationship_type": "many-to-one",
                    "join_columns": {"date_id": "date_id"},
                    "description": "Many performance records belong to one date"
                },
                {
                    "related_table": "DIM_EMPLOYEE",
                    "relationship_type": "many-to-one",
                    "join_columns": {"employee_id": "employee_id"},
                    "description": "Many performance records belong to one employee"
                },
                {
                    "related_table": "DIM_STORE",
                    "relationship_type": "many-to-one",
                    "join_columns": {"store_id": "store_id"},
                    "description": "Many performance records belong to one store"
                }
            ]
        },
        {
            "table_name": "FACT_INVENTORY",
            "table_description": "Inventory fact table for stock level analysis, with quantities and costs.",
            "Use Case": "Use this table for stock level monitoring, inventory turnover analysis, and stockout prevention.",
            "relationships": [
                {
                    "related_table": "DIM_DATE",
                    "relationship_type": "many-to-one",
                    "join_columns": {"date_id": "date_id"},
                    "description": "Many inventory records belong to one date"
                },
                {
                    "related_table": "DIM_STORE",
                    "relationship_type": "many-to-one",
                    "join_columns": {"store_id": "store_id"},
                    "description": "Many inventory records maintained by one store"
                },
                {
                    "related_table": "DIM_PRODUCT",
                    "relationship_type": "many-to-one",
                    "join_columns": {"product_id": "product_id"},
                    "description": "Many inventory records for one product"
                }
            ]
        },
        {
            "table_name": "FACT_PURCHASE_ORDERS",
            "table_description": "Purchase orders fact table for procurement analysis.",
            "Use Case": "Use this table for procurement analysis, supplier performance, and order fulfillment studies.",
            "relationships": [
                {
                    "related_table": "DIM_DATE",
                    "relationship_type": "many-to-one",
                    "join_columns": {"date_id": "date_id"},
                    "description": "Many purchase orders belong to one date"
                },
                {
                    "related_table": "DIM_SUPPLIER",
                    "relationship_type": "many-to-one",
                    "join_columns": {"supplier_id": "supplier_id"},
                    "description": "Many purchase orders placed with one supplier"
                },
                {
                    "related_table": "DIM_PRODUCT",
                    "relationship_type": "many-to-one",
                    "join_columns": {"product_id": "product_id"},
                    "description": "Many purchase orders for one product"
                }
            ]
        },
        {
            "table_name": "FACT_SALES",
            "table_description": "Sales fact table for transaction analysis with pricing, quantities, and margins.",
            "Use Case": "Use this table for sales performance analysis, profitability studies, and customer purchasing behavior.",
            "relationships": [
                {
                    "related_table": "DIM_DATE",
                    "relationship_type": "many-to-one",
                    "join_columns": {"date_id": "date_id"},
                    "description": "Many sales belong to one date"
                },
                {
                    "related_table": "DIM_STORE",
                    "relationship_type": "many-to-one",
                    "join_columns": {"store_id": "store_id"},
                    "description": "Many sales generated by one store"
                },
                {
                    "related_table": "DIM_PRODUCT",
                    "relationship_type": "many-to-one",
                    "join_columns": {"product_id": "product_id"},
                    "description": "Many sales include one product"
                },
                {
                    "related_table": "DIM_CUSTOMER",
                    "relationship_type": "many-to-one",
                    "join_columns": {"customer_id": "customer_id"},
                    "description": "Many sales made by one customer"
                },
                {
                    "related_table": "DIM_PROMOTION",
                    "relationship_type": "many-to-one",
                    "join_columns": {"promotion_id": "promotion_id"},
                    "description": "Many sales applied with one promotion"
                },
                {
                    "related_table": "DIM_EMPLOYEE",
                    "relationship_type": "many-to-one",
                    "join_columns": {"employee_id": "employee_id"},
                    "description": "Many sales processed by one employee"
                }
            ]
        }
    ]
}
semantic_model_str = json.dumps(semantic_model, indent=2)
# *******************************


def get_sql_agent(
    name: str = "SQL Agent",
    user_id: Optional[str] = None,
    model_id: str = "openai:gpt-4o",
    session_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Agent:
    """Returns an instance of the SQL Agent.

    Args:
        user_id: Optional user identifier
        debug_mode: Enable debug logging
        model_id: Model identifier in format 'provider:model_name'
    """
    # Parse model provider and name
    provider, model_name = model_id.split(":")

    # Select appropriate model class based on provider
    if provider == "openai":
        model = OpenAIChat(id=model_name)
    elif provider == "google":
        model = Gemini(id=model_name)
    elif provider == "anthropic":
        model = Claude(id=model_name)
    elif provider == "groq":
        model = Groq(id=model_name)
    else:
        raise ValueError(f"Unsupported model provider: {provider}")

    return Agent(
        name=name,
        model=model,
        user_id=user_id,
        session_id=session_id,
        storage=agent_storage,
        knowledge=agent_knowledge,
        # Enable Agentic RAG i.e. the ability to search the knowledge base on-demand
        search_knowledge=True,
        # Enable the ability to read the chat history
        read_chat_history=True,
        # Enable the ability to read the tool call history
        read_tool_call_history=True,
        # Add tools to the agent
        tools=[
            SQLTools(db_url=db_url, list_tables=False),
            FileTools(base_dir=output_dir),
        ],
        debug_mode=debug_mode,
        description=dedent("""\
        You are RetailIQ, an elite Text2SQL Engine specializing in:

        - Sales performance analysis
        - Inventory management insights
        - Customer behavior analytics
        - Product profitability metrics
        - Store performance evaluation
        - Promotional campaign effectiveness

        You combine deep retail knowledge with advanced SQL expertise to uncover insights from comprehensive inventory and sales data."""),
        instructions=dedent(f"""\
        You are a SQL expert focused on writing precise, efficient queries.

        When a user messages you, determine if you need query the database or can respond directly.
        If you can respond directly, do so.

        If you need to query the database to answer the user's question, follow these steps:
        1. First identify the tables you need to query from the semantic model.
        2. Then, ALWAYS use the `search_knowledge_base(table_name)` tool to get table metadata, rules and sample queries.
        3. If table rules are provided, ALWAYS follow them.
        4. Then, "think" about query construction, don't rush this step.
        5. Follow a chain of thought approach before writing SQL, ask clarifying questions where needed.
        6. If sample queries are available, use them as a reference.
        7. If you need more information about the table, use the `describe_table` tool.
        8. Then, using all the information available, create one single syntactically correct PostgreSQL query to accomplish your task.
        9. If you need to join tables, check the `semantic_model` for the relationships between the tables.
            - If the `semantic_model` contains a relationship between tables, use that relationship to join the tables even if the column names are different.
            - If you cannot find a relationship in the `semantic_model`, only join on the columns that have the same name and data type.
            - If you cannot find a valid relationship, ask the user to provide the column name to join.
        10. If you cannot find relevant tables, columns or relationships, stop and ask the user for more information.
        11. Once you have a syntactically correct query, run it using the `run_sql_query` function.
        12. When running a query:
            - Be careful with the case of table names and column names. Make sure to use the correct case. You can use the `describe_table` tool to get the correct case.
            - The table name must be put inside the quotation marks. For example: SELECT ... FROM "<table_name>" WHERE ...
            - Do not add a `;` at the end of the query.
            - Always provide a limit unless the user explicitly asks for all results.
        13. After you run the query, "analyze" the results and return the answer in markdown format.
        14. Make sure to always "analyze" the results of the query before returning the answer.
        15. You Analysis should Reason about the results of the query, whether they make sense, whether they are complete, whether they are correct, could there be any data quality issues, etc.
        16. It is really important that you "analyze" and "validate" the results of the query.
        17. Always show the user the SQL you ran to get the answer.
        18. Continue till you have accomplished the task.
        19. Show results as a table or a chart if possible.

        After finishing your task, ask the user relevant followup questions like "was the result okay, would you like me to fix any problems?"
        If the user says yes, get the previous query using the `get_tool_call_history(num_calls=3)` function and fix the problems.
        If the user wants to see the SQL, get it using the `get_tool_call_history(num_calls=3)` function.

        Finally, here are the set of rules that you MUST follow:

        <rules>
        - Use the `search_knowledge_base(table_name)` tool to get table information from your knowledge base before writing a query.
        - Do not use phrases like "based on the information provided" or "from the knowledge base".
        - Always show the SQL queries you use to get the answer.
        - Make sure your query accounts for duplicate records.
        - Make sure your query accounts for null values.
        - If you run a query, explain why you ran it.
        - Always derive your answer from the data and the query.
        - **NEVER, EVER RUN CODE TO DELETE DATA OR ABUSE THE LOCAL SYSTEM**
        - ALWAYS FOLLOW THE `table rules` if provided. NEVER IGNORE THEM.
        </rules>\
        """),
        additional_context=dedent("""\n
        The `semantic_model` contains information about tables and the relationships between them.
        If the users asks about the tables you have access to, simply share the table names from the `semantic_model`.
        <semantic_model>
        """)
        + semantic_model_str
        + dedent("""
        </semantic_model>\
        """),
    )
