import asyncio
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from flask import Blueprint, render_template, request, jsonify
import os
import json
from openai import AsyncOpenAI
import matplotlib
import logging
import traceback
from datetime import datetime
matplotlib.use('Agg')  # Use non-interactive backend

# Set up logging
log_file = f"report_ai_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
# Fix: Pass API key directly instead of using os.getenv incorrectly
api_key = "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"
openai_client = AsyncOpenAI(api_key=api_key)

# Create Blueprint for reports
reports_bp = Blueprint('reports', __name__)


# Database path
DB_PATH = 'instance/task_manager.db'

# Schema information for context
SCHEMA_INFO = """
Tables in the database:
1. tasks
   - Task_id (String): Primary key, UUID
   - Display_id (String): Unique identifier (e.g., "LGL-JOB-001")
   - Dept_name (String): Department name
   - Category (String): Task category
   - Sub_category (String): Task subcategory
   - Date_Created (DateTime): When task was created
   - Description (String): Task description
   - Date_Modified (DateTime): When task was last modified
   - Estimated_time (Float): Estimated time for completion

2. task_logs
   - Log_id (Integer): Primary key
   - Task_id (String): Foreign key to tasks.Task_id
   - User_name (String): Name of user who logged time
   - time_taken (Float): Time spent on the task
   - log_date (DateTime): When the log was recorded
"""

# Define the tools that can be used by the AI
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql_query",
            "description": "Execute a SQL query on the database",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_visualization",
            "description": "Create a visualization from data",
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {
                        "type": "string",
                        "description": "Type of chart (bar, line, pie, etc.)"
                    },
                    "data": {
                        "type": "string",
                        "description": "The data to visualize (as SQL query)"
                    }
                },
                "required": ["chart_type", "data"]
            }
        }
    }
]

# Define the functions that can be called by the AI
def execute_sql_query(query: str) -> str:
    """Execute the SQL query and return the results as JSON"""
    logger.info(f"Executing SQL query: {query}")
    try:
        # Verify database exists
        if not os.path.exists(DB_PATH):
            error_msg = f"Database file not found at path: {DB_PATH}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
            
        # Detailed logging of database connection
        try:
            logger.info(f"Attempting to connect to database at {DB_PATH}")
            conn = sqlite3.connect(DB_PATH)
            logger.info(f"Successfully connected to database at {DB_PATH}")
        except Exception as conn_error:
            error_msg = f"Database connection error: {str(conn_error)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return json.dumps({"error": error_msg})
        
        # Add more detailed logging for query execution
        cursor = conn.cursor()
        try:
            # First check if we can execute the query without fetching
            logger.info(f"Testing query execution: {query}")
            cursor.execute(query)
            logger.info("Query syntax validated successfully")
        except sqlite3.Error as e:
            error_msg = f"SQL syntax error: {str(e)}"
            logger.error(error_msg)
            conn.close()
            logger.info("Database connection closed after error")
            return json.dumps({"error": error_msg})
        
        # Now try to get results with pandas
        try:
            logger.info(f"Executing query with pandas: {query}")
            df = pd.read_sql_query(query, conn)
            row_count = len(df)
            col_count = len(df.columns)
            logger.info(f"Query returned {row_count} rows and {col_count} columns")
            
            # Log a sample of the data
            if row_count > 0:
                sample = df.head(3).to_dict(orient="records")
                logger.debug(f"Sample data: {json.dumps(sample)}")
            else:
                logger.warning("Query returned no data")
                # Return an empty array as valid JSON instead of an empty string
                conn.close()
                logger.info("Database connection closed")
                return json.dumps([])
            
            # Convert the DataFrame to JSON
            result = df.to_json(orient="records")
            logger.debug(f"Successfully converted result to JSON, length: {len(result)}")
            
            # Verify the result is valid JSON before returning
            try:
                # Test parse to ensure it's valid
                json.loads(result)
                logger.debug("Result validated as valid JSON")
            except json.JSONDecodeError as je:
                logger.error(f"Result is not valid JSON: {je}")
                # Return a valid JSON error object instead
                conn.close()
                logger.info("Database connection closed after JSON validation error")
                return json.dumps({"error": "Result could not be converted to valid JSON"})
                
            conn.close()
            logger.info("Database connection closed successfully")
            return result
        except Exception as e:
            error_msg = f"Error processing query results: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            conn.close()
            logger.info("Database connection closed after error")
            return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Error executing SQL query: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return json.dumps({"error": error_msg})

def create_visualization(chart_type: str, data: str) -> str:
    """Return data in tabular format without generating any chart"""
    logger.info(f"Requested visualization: chart_type={chart_type}, processing as tabular data only")
    try:
        # If data is an SQL query, execute it first
        if isinstance(data, str) and data.strip().upper().startswith("SELECT"):
            logger.info(f"Data is an SQL query, executing: {data}")
            data_json = execute_sql_query(data)
            logger.debug(f"SQL query result: {data_json[:100]}...")
        else:
            data_json = data
        
        # Validate the data is proper JSON
        try:
            parsed_data = json.loads(data_json)
            if isinstance(parsed_data, dict) and "error" in parsed_data:
                # If SQL execution failed, log and return error
                logger.error(f"Error in data: {parsed_data['error']}")
                return json.dumps({"error": parsed_data['error']})
                
            # Just return the data with some metadata
            if isinstance(parsed_data, list):
                row_count = len(parsed_data)
                col_names = list(parsed_data[0].keys()) if row_count > 0 else []
                logger.info(f"Processed tabular data: {row_count} rows, {len(col_names)} columns")
                
                return json.dumps({
                    "data": parsed_data,
                    "title": f"Data results for {chart_type} format",
                    "columns": col_names,
                    "row_count": row_count
                })
            else:
                logger.warning(f"Data is not in expected list format: {type(parsed_data)}")
                return json.dumps({"error": "Data is not in expected format for tabular display"})
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON data: {e}")
            return json.dumps({"error": f"Invalid data format: {str(e)}"})
    except Exception as e:
        logger.error(f"Error in create_visualization: {str(e)}")
        logger.error(traceback.format_exc())
        return json.dumps({"error": f"Error processing visualization request: {str(e)}"})

# Update the FUNCTION_MAP to use the correct implementations
FUNCTION_MAP = {
    "execute_sql_query": execute_sql_query,
    "create_visualization": create_visualization
}

# Function to generate SQL based on user question
async def generate_sql_for_question(question):
    system_prompt = f"""You are a SQL expert. Generate a valid SQLite SQL query based on the user's question.
{SCHEMA_INFO}

IMPORTANT: Use only simple SQLite-compatible syntax. Avoid complex functions like DATE_TRUNC.
For date functions, use SQLite functions like strftime() instead.
For example, to group by month, use: strftime('%Y-%m', Date_Created)

Respond with ONLY the SQL query, no explanations or other text. Also
never display the Task_id or Log_id in the result of the query. Use the Display_id instead."""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.1
        )
        sql_query = response.choices[0].message.content.strip()
        # Remove any markdown code blocks if present
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
        return sql_query
    except Exception as e:
        return f"Error generating SQL: {str(e)}"

async def generate_sql_query(question: str) -> str:
    """Generate a SQL query based on a question about tasks or logs"""
    sql_query = await generate_sql_for_question(question)
    return sql_query

async def analyze_results(question: str, data_json: str) -> str:
    """Analyze the data and determine what type of visualization would be appropriate"""
    system_prompt = f"""You're a data visualization expert. Based on the user's question and the data provided, 
recommend the best visualization approach. The data is from a legal task management system.

{SCHEMA_INFO}

Respond with a JSON object containing:
- visualization_type: One of ['bar', 'line', 'pie', 'scatter', 'none']
- title: Title for the visualization
- x_label: Column to use for x-axis
- y_label: Column to use for y-axis
- explanation: Brief explanation of why this visualization is appropriate
"""

    try:
        # Parse data to describe it
        data = json.loads(data_json)
        df = pd.DataFrame(data)
        data_description = f"Data contains {len(df)} rows and {len(df.columns)} columns: {', '.join(df.columns)}"
        
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Question: {question}\nData: {data_description}"}
            ]
        )
        
        recommendation = response.choices[0].message.content
        # Try to extract JSON from response
        try:
            # Find JSON in the response - it might be wrapped in markdown code blocks
            if "```json" in recommendation:
                json_content = recommendation.split("```json")[1].split("```")[0].strip()
            elif "```" in recommendation:
                json_content = recommendation.split("```")[1].strip()
            else:
                json_content = recommendation
                
            vis_details = json.loads(json_content)
            return json.dumps(vis_details)
        except:
            # If proper JSON parsing fails, return a default structure
            return json.dumps({
                "visualization_type": "bar",
                "title": "Results Visualization",
                "x_label": df.columns[0] if len(df.columns) > 0 else "",
                "y_label": df.columns[1] if len(df.columns) > 1 else "",
                "explanation": "Default visualization as JSON parsing failed"
            })
    except Exception as e:
        return json.dumps({
            "visualization_type": "none",
            "title": "",
            "x_label": "",
            "y_label": "",
            "explanation": f"Error analyzing results: {str(e)}"
        })

# Routes for the reports page
@reports_bp.route('/reports')
def reports():
    return render_template('reports.html')

@reports_bp.route('/api/ask_report', methods=['POST'])
async def ask_report():
    data = request.json
    question = data.get('question', '')
    
    logger.info(f"Received report question: '{question}'")
    
    try:
        # Process the question using function calling
        result = await process_question(question)
        logger.info(f"Returning result with {len(result.keys())} keys")
        
        # Log the keys in the result to debug
        logger.debug(f"Result keys: {list(result.keys())}")
        
        # Check if we got an error
        if 'error' in result:
            logger.error(f"Error in result: {result['error']}")
        
        return jsonify(result)
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Exception in ask_report: {str(e)}")
        logger.error(error_trace)
        return jsonify({"error": str(e), "traceback": error_trace}), 500

# Add this function to create the layout template as well
def create_layout_template():
    os.makedirs('templates', exist_ok=True)
    
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Legal Task System</title>
        <!-- Bootstrap CSS -->
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
        <!-- Custom CSS -->
        <style>
            body {
                padding-top: 20px;
                padding-bottom: 40px;
            }
            .navbar {
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <nav class="navbar navbar-expand-lg navbar-light bg-light rounded">
                <div class="container-fluid">
                    <a class="navbar-brand" href="/">Legal Task System</a>
                    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                        <span class="navbar-toggler-icon"></span>
                    </button>
                    <div class="collapse navbar-collapse" id="navbarNav">
                        <ul class="navbar-nav">
                            <li class="nav-item">
                                <a class="nav-link" href="/">Dashboard</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" href="/task/new">New Task</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" href="/reports">Reports</a>
                            </li>
                        </ul>
                    </div>
                </div>
            </nav>

            <!-- Flash messages -->
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <!-- Main content -->
            {% block content %}{% endblock %}
        </div>

        <!-- Bootstrap JS -->
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    
    with open('templates/layout.html', 'w') as f:
        f.write(html_content)

# Update the init_reports function to create both templates
def init_reports(app):
    create_layout_template()  # Create the layout template first
    create_reports_template()
    app.register_blueprint(reports_bp)
    # Remove MCP server start
    # start_mcp_server()

# Create a template for the reports page
def create_reports_template():
    os.makedirs('templates', exist_ok=True)
    
    html_content = """
    {% extends 'layout.html' %}
    
    {% block content %}
    <div class="container mt-5">
        <h1>Task Reports</h1>
        <p>Ask questions about tasks and get insights from the data. You can also ask general questions!</p>
        
        <div class="card mb-4">
            <div class="card-body">
                <div class="input-group mb-3">
                    <input type="text" id="questionInput" class="form-control" 
                           placeholder="Ask a question about tasks (e.g., 'Show me tasks by department') or any general question">
                    <button class="btn btn-primary" id="askButton">Ask</button>
                </div>
            </div>
        </div>
        
        <div id="loadingIndicator" class="text-center d-none">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p>Analyzing your question and generating insights...</p>
        </div>
        
        <!-- General response container for non-report questions -->
        <div id="generalResponseContainer" class="d-none">
            <div class="card mb-4">
                <div class="card-header">
                    <h5>Response</h5>
                </div>
                <div class="card-body">
                    <div id="generalResponse"></div>
                </div>
            </div>
        </div>
        
        <!-- Report results container -->
        <div id="resultsContainer" class="d-none">
            <!-- AI Summary -->
            <div class="card mb-4">
                <div class="card-header">
                    <h5>AI Analysis</h5>
                </div>
                <div class="card-body">
                    <div id="aiSummary" class="mb-3"></div>
                </div>
            </div>
            
            <!-- SQL Query -->
            <div class="card mb-4">
                <div class="card-header">
                    <h5>SQL Query</h5>
                </div>
                <div class="card-body">
                    <pre id="sqlQuery" class="bg-light p-3 rounded"></pre>
                </div>
            </div>
            
            <!-- Results Table -->
            <div class="card mb-4">
                <div class="card-header">
                    <h5>Results</h5>
                </div>
                <div class="card-body">
                    <div id="tableResults" class="table-responsive"></div>
                </div>
            </div>
            
            <!-- Visualization -->
            <div id="visualizationCard" class="card mb-4 d-none">
                <div class="card-header">
                    <h5 id="visualizationTitle">Visualization</h5>
                </div>
                <div class="card-body text-center">
                    <img id="visualizationImage" class="img-fluid" src="" alt="Visualization">
                    <p id="visualizationExplanation" class="mt-3 text-muted"></p>
                </div>
            </div>
        </div>
        
        <div id="errorContainer" class="alert alert-danger d-none"></div>
    </div>
    
    <script>
        document.getElementById('askButton').addEventListener('click', async function() {
            const question = document.getElementById('questionInput').value.trim();
            if (!question) return;
            
            // Show loading, hide previous results
            document.getElementById('loadingIndicator').classList.remove('d-none');
            document.getElementById('resultsContainer').classList.add('d-none');
            document.getElementById('generalResponseContainer').classList.add('d-none');
            document.getElementById('errorContainer').classList.add('d-none');
            
            try {
                const response = await fetch('/api/ask_report', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ question: question })
                });
                
                const result = await response.json();
                
                if (result.error) {
                    throw new Error(result.error);
                }
                
                // Check if this is a report-related question or general question
                if (!result.is_report_related) {
                    // Display general response
                    document.getElementById('generalResponse').innerHTML = result.summary || 'No response provided.';
                    document.getElementById('generalResponseContainer').classList.remove('d-none');
                } else {
                    // Display AI summary
                    document.getElementById('aiSummary').innerHTML = result.summary || 'No summary provided.';
                    
                    // Display SQL query
                    document.getElementById('sqlQuery').textContent = result.sql_query || 'No SQL query generated.';
                    
                    // Create table from data
                    const tableResults = document.getElementById('tableResults');
                    tableResults.innerHTML = '';
                    
                    if (result.data && result.data.length > 0) {
                        const table = document.createElement('table');
                        table.className = 'table table-striped table-hover';
                        
                        // Create header
                        const thead = document.createElement('thead');
                        const headerRow = document.createElement('tr');
                        
                        Object.keys(result.data[0]).forEach(key => {
                            const th = document.createElement('th');
                            th.textContent = key;
                            headerRow.appendChild(th);
                        });
                        
                        thead.appendChild(headerRow);
                        table.appendChild(thead);
                        
                        // Create body
                        const tbody = document.createElement('tbody');
                        
                        result.data.forEach(row => {
                            const tr = document.createElement('tr');
                            
                            Object.values(row).forEach(value => {
                                const td = document.createElement('td');
                                td.textContent = value;
                                tr.appendChild(td);
                            });
                            
                            tbody.appendChild(tr);
                        });
                        
                        table.appendChild(tbody);
                        tableResults.appendChild(table);
                    } else {
                        tableResults.innerHTML = '<p>No data found for the query.</p>';
                    }
                    
                    // Handle visualization if present
                    const visualizationCard = document.getElementById('visualizationCard');
                    
                    if (result.visualization && result.visualization.tabular_data) {
                        // Show tabular data instead of image
                        document.getElementById('visualizationTitle').textContent = 
                            result.visualization.title || 'Data Results';
                        
                        // Create a table for the tabular data
                        const tableDiv = document.createElement('div');
                        tableDiv.className = 'table-responsive';
                        
                        const table = document.createElement('table');
                        table.className = 'table table-striped table-hover';
                        
                        // Create table from the tabular data
                        if (result.visualization.tabular_data.length > 0) {
                            // Create header
                            const thead = document.createElement('thead');
                            const headerRow = document.createElement('tr');
                            
                            Object.keys(result.visualization.tabular_data[0]).forEach(key => {
                                const th = document.createElement('th');
                                th.textContent = key;
                                headerRow.appendChild(th);
                            });
                            
                            thead.appendChild(headerRow);
                            table.appendChild(thead);
                            
                            // Create body
                            const tbody = document.createElement('tbody');
                            
                            result.visualization.tabular_data.forEach(row => {
                                const tr = document.createElement('tr');
                                
                                Object.values(row).forEach(value => {
                                    const td = document.createElement('td');
                                    td.textContent = value;
                                    tr.appendChild(td);
                                });
                                
                                tbody.appendChild(tr);
                            });
                            
                            table.appendChild(tbody);
                        } else {
                            tableDiv.innerHTML = '<p>No data available for display</p>';
                        }
                        
                        tableDiv.appendChild(table);
                        
                        // Clear any existing content and add the table
                        const imageContainer = document.getElementById('visualizationImage').parentElement;
                        imageContainer.innerHTML = '';
                        imageContainer.appendChild(tableDiv);
                        
                        document.getElementById('visualizationExplanation').textContent = 
                            `Showing ${result.visualization.row_count} rows of data`;
                        
                        visualizationCard.classList.remove('d-none');
                    } else if (result.visualization && result.visualization.image) {
                        // The old image-based visualization handling (keep this as fallback)
                        document.getElementById('visualizationTitle').textContent = 
                            (result.visualization_details && result.visualization_details.title) || 'Visualization';
                        document.getElementById('visualizationImage').src = 'data:image/png;base64,' + result.visualization.image;
                        document.getElementById('visualizationExplanation').textContent = 
                            (result.visualization_details && result.visualization_details.explanation) || '';
                        visualizationCard.classList.remove('d-none');
                    } else {
                        visualizationCard.classList.add('d-none');
                    }
                    
                    // Show results
                    document.getElementById('resultsContainer').classList.remove('d-none');
                }
            } catch (error) {
                console.error(error);
                const errorContainer = document.getElementById('errorContainer');
                errorContainer.textContent = 'Error: ' + error.message;
                errorContainer.classList.remove('d-none');
            } finally {
                document.getElementById('loadingIndicator').classList.add('d-none');
            }
        });
        
        // Allow pressing Enter to submit question
        document.getElementById('questionInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('askButton').click();
            }
        });
    </script>
    {% endblock %}
    """
    
    with open('templates/reports.html', 'w') as f:
        f.write(html_content)

# Add this function to handle general queries
async def handle_general_query(question: str) -> str:
    """Handle questions unrelated to reports by using OpenAI directly"""
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Answer the user's question directly and concisely."},
                {"role": "user", "content": question}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error processing general query: {str(e)}"

# Update the process_question function
async def process_question(question):
    """Process a question using function calling or direct query for non-report questions"""
    logger.info(f"Processing question: '{question}'")
    try:
        # First, let's determine if this is a report-related question
        logger.debug("Checking if question is report-related")
        is_report_related = await check_if_report_related(question)
        logger.info(f"Is report related: {is_report_related}")
        
        if not is_report_related:
            # For non-report questions, use direct OpenAI
            logger.info("Handling as general query")
            answer = await handle_general_query(question)
            logger.debug(f"Got general answer: {answer[:100]}...")
            return {
                "question": question,
                "is_report_related": False,
                "summary": answer
            }
        
        # Continue with existing report-related processing
        logger.info("Processing as report-related query")
        conversation = [
            {"role": "system", "content": f"""You are an AI assistant with expertise in SQL and data analysis.
You have access to a database of legal tasks with the following schema:
{SCHEMA_INFO}

IMPORTANT: 
1. Generate ONLY simple SQLite-compatible queries. 
2. Use strftime() for date functions, not DATE_TRUNC.
   Example: strftime('%Y-%m', Date_Created) instead of DATE_TRUNC('month', Date_Created)
3. Keep queries simple and straightforward.

To answer user questions, follow these steps:
1. Generate a simple SQL query based on the user's question
2. Execute the SQL query using execute_sql_query
3. If visualization would be helpful, use create_visualization
4. Summarize the results in a clear and concise way
5. Only answer with the results of the query, no other text"""
            },
            {"role": "user", "content": question}
        ]
        
        # Initial call to get function call
        logger.debug("Making initial call to OpenAI for function suggestions")
        response = await openai_client.chat.completions.create(
            model="gpt-4o",  # Using a more capable model for function calling
            messages=conversation,
            tools=TOOLS,
            tool_choice="auto"
        )
        
        logger.debug(f"Initial response received: {response.model_dump_json()[:200]}...")
        
        assistant_message = response.choices[0].message
        conversation.append(assistant_message)
        
        # Process all function calls until the model stops calling functions
        function_call_results = []
        
        while assistant_message.tool_calls:
            # Process each tool call
            logger.info(f"Processing {len(assistant_message.tool_calls)} tool calls")
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Executing function: {function_name} with args: {function_args}")
                
                # Execute the function
                function_to_call = FUNCTION_MAP[function_name]
                function_response = function_to_call(**function_args)
                
                # Fix the logging by checking if function_response exists and is a string
                if function_response is not None and isinstance(function_response, str):
                    logger.debug(f"Function response: {function_response[:100]}...")
                else:
                    logger.debug(f"Function response: {str(function_response)}")
                
                # Save results for the final response
                function_call_results.append({
                    "function": function_name,
                    "args": function_args,
                    "result": function_response if function_response is not None else ""
                })
                
                # FIXED: Ensure content is always a string for tool messages
                function_response_str = str(function_response) if function_response is not None else ""
                
                # Add the function response to the conversation with proper formatting
                conversation.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response_str  # Always provide a string here
                })
            
            # Call the API again to get the next action
            logger.debug("Making follow-up call to OpenAI")
            response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=conversation,
                tools=TOOLS,
                tool_choice="auto"
            )
            
            assistant_message = response.choices[0].message
            logger.debug(f"Follow-up response received from OpenAI")
            conversation.append(assistant_message)
        
        # Final response from the model after all function calls
        final_response = assistant_message.content
        logger.info(f"Final AI response: {final_response[:100]}...")
        
        # Process function results to extract visualization if available
        visualization = None
        data = None
        sql_query = None
        
        logger.debug("Processing function results")
        for result in function_call_results:
            if result["function"] == "execute_sql_query":
                try:
                    result_str = result["result"]
                    logger.debug(f"Raw SQL result: {result_str[:200]}")
                    
                    # Check if the result is an error message
                    try:
                        parsed_result = json.loads(result_str)
                        
                        # Check if the result contains an error
                        if isinstance(parsed_result, dict) and "error" in parsed_result:
                            logger.error(f"SQL execution returned error: {parsed_result['error']}")
                            data = []  # Set empty data array
                        # Check if we got an empty array
                        elif isinstance(parsed_result, list) and len(parsed_result) == 0:
                            logger.warning("SQL query returned empty result set")
                            data = []
                        else:
                            # Normal results
                            data = parsed_result
                            logger.info(f"Extracted {len(data)} records from SQL result")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse SQL result JSON: {e}")
                        logger.error(f"Invalid JSON was: {result_str[:100]}...")
                        data = []
                        
                    sql_query = result["args"]["query"]
                except Exception as e:
                    logger.error(f"Failed to process SQL result: {e}")
                    logger.error(traceback.format_exc())
                    data = []
            elif result["function"] == "generate_sql_query":
                sql_query = result["result"]
                logger.info(f"Extracted SQL query: {sql_query}")
            elif result["function"] == "create_visualization":
                try:
                    vis_result = json.loads(result["result"])
                    if "data" in vis_result and not "error" in vis_result:
                        # Store the data for tabular display instead of visualization image
                        if visualization is None:  # Only set if not already set
                            visualization = {
                                "tabular_data": vis_result["data"],
                                "title": vis_result.get("title", "Data Results"),
                                "row_count": vis_result.get("row_count", 0)
                            }
                        logger.info("Tabular data extracted from visualization request")
                    elif "error" in vis_result:
                        logger.warning(f"Visualization error: {vis_result['error']}")
                except Exception as e:
                    logger.error(f"Failed to parse visualization result: {e}")
        
        # Prepare visualization details from analysis function
        visualization_details = None
        for result in function_call_results:
            if result["function"] == "analyze_data_for_visualization":
                try:
                    visualization_details = json.loads(result["result"])
                    logger.info(f"Visualization details: {visualization_details}")
                except Exception as e:
                    logger.error(f"Failed to parse visualization details: {e}")
                    visualization_details = {"visualization_type": "none"}
        
        result = {
            "question": question,
            "is_report_related": True,
            "sql_query": sql_query,
            "data": data,
            "visualization": visualization,
            "visualization_details": visualization_details,
            "summary": final_response,
            "function_calls": function_call_results
        }
        
        logger.info("Request processing completed successfully")
        return result
    except Exception as e:
        logger.error(f"Error processing question: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": f"Error processing question: {str(e)}\n{traceback.format_exc()}"}

# Add function to check if a question is related to reports/database
async def check_if_report_related(question: str) -> bool:
    """Determine if a question is related to reports or database queries"""
    logger.debug(f"Checking if question is report-related: '{question}'")
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"""You are an AI assistant that determines if a question is related to database queries or reports.
The database contains information about legal tasks with this schema:
{SCHEMA_INFO}

A question is considered report-related if:
1. It asks about tasks, logs, departments, users, or other entities in the database
2. It requests statistics, counts, or trends related to the data
3. It asks for visualizations of the data
4. It mentions SQL or queries related to the data

Respond with ONLY 'true' if the question is report-related or 'false' if it's a general question unrelated to the database."""},
                {"role": "user", "content": question}
            ],
            temperature=0.1
        )
        
        answer = response.choices[0].message.content.strip().lower()
        logger.info(f"Report related check result: '{answer}'")
        return answer == 'true'
    except Exception as e:
        logger.error(f"Error in check_if_report_related: {str(e)}")
        logger.error(traceback.format_exc())
        # Default to assuming it's report-related if we can't determine
        return True

# Add a debug route to quickly check if the app is working
@reports_bp.route('/api/debug', methods=['GET'])
def api_debug():
    logger.info("Debug endpoint called")
    try:
        # Check if database exists
        db_exists = os.path.exists(DB_PATH)
        logger.info(f"Database exists: {db_exists}")
        
        # Try to connect and count records
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get table counts
        task_count = cursor.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        log_count = cursor.execute("SELECT COUNT(*) FROM task_logs").fetchone()[0]
        
        # Get table schemas
        tasks_schema = cursor.execute("PRAGMA table_info(tasks)").fetchall()
        logs_schema = cursor.execute("PRAGMA table_info(task_logs)").fetchall()
        
        conn.close()
        
        return jsonify({
            "status": "ok",
            "database": {
                "exists": db_exists,
                "path": DB_PATH,
                "task_count": task_count,
                "log_count": log_count,
                "tasks_schema": tasks_schema,
                "logs_schema": logs_schema
            },
            "api_key_set": bool(api_key),
            "log_file": log_file
        })
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "database_path": DB_PATH,
            "database_exists": os.path.exists(DB_PATH) if 'DB_PATH' in globals() else "Unknown"
        }), 500

if __name__ == "__main__":
    # Remove MCP code
    print("Starting report_ai in standalone mode")
