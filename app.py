from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from models import db, Tasks, TaskLogs
from config import Config
from sqlalchemy import func
from datetime import datetime
import re
import json
import requests
import os

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Replace the deprecated before_first_request decorator
with app.app_context():
    db.create_all()

def generate_display_id():
    # Get the highest Display_id number or start with 0
    last_task = Tasks.query.order_by(Tasks.Display_id.desc()).first()
    
    if last_task and re.match(r"LGL-JOB-\d+", last_task.Display_id):
        last_number = int(last_task.Display_id.split('-')[-1])
        new_number = last_number + 1
    else:
        new_number = 1
    
    # Format with leading zeros
    return f"LGL-JOB-{new_number:03d}"

@app.context_processor
def inject_constants():
    # Department options
    departments = [
        "BD Small to Mid scale",
        "BD Large scale",
        "Project Development",
        "HR",
        "Procurement",
        "Strategy",
        "Corporate Finance",
        "Proposal Engineering & Bidding Team",
        "Admin",
        "Miscellaneous"
    ]
    
    # Lookup data for categories, subcategories and estimated times
    category_data = {
        "Non-Disclosure Agreements": {
            "Review of NDA (if in Company's standard draft)": 2,
            "Review of NDA (if in Client's draft)": 3.2
        },
        "Consultant Agreements": {
            "Employment Agreement": 9,
            "House-Keeping Agreement": 6
        },
        "Engagement Letters": {
            "Banks, auditors, law firms": 19,
            "Consultants": 19,
            "Technical Consultants": 19
        },
        "Memorandum of Understanding": {
            "Domestic": 6.5,
            "International": 18
        },
        "Letter of Intent": {
            "In standard draft of Company (Procurement)": 3.5,
            "Draft from client (Procurement)": 7,
            "Draft from client (Projects)": 24,
            "Draft from client (BD team)": 20
        },
        "Supply Agreements": {
            "For Electrolyser": 25,
            "For Compressor/Rectifier": 8
        },
        "Term Sheets": {
            "Domestic": 22.5,
            "International": 45
        },
        "Right to Use Agreements": {
            "Drafting/Reviewing": 17
        },
        "Gas Purchase Agreements": {
            "Drafting/Reviewing": 110
        },
        "Merchant Agreements": {
            "If in Standard draft of Company": 5.5,
            "If in Client's draft": 40
        },
        "Loan Agreements including the security documents": {
            "Drafting/Reviewing": 100
        },
        "Bank Guarantees (PBGs, CBGs, ABGs)": {
            "If in Standard draft of Company": 9,
            "If in Client's draft": 9
        },
        "EPC Agreements": {
            "Reviewing draft from client": 55
        },
        "O&M Agreements": {
            "Reviewing draft from client": 55
        },
        "Power Purchase Agreements": {
            "Drafting/Reviewing/Finalization": 72.5
        },
        "EPCM Agreements": {
            "Drafting/Reviewing": 125
        },
        "Master Development Agreements": {
            "Drafting/Reviewing": 80
        },
        "Deed of Assignments": {
            "Drafting/Reviewing": 7
        },
        "Rent Agreements": {
            "Drafting/Reviewing": 3
        },
        "Lease Deed/Sale Deed/Agreement to Lease/Agreement to Sell": {
            "Drafting/Reviewing": 17
        },
        "Service Agreements": {
            "In Company's draft": 11,
            "In Client's draft": 14
        },
        "Letter of Authority": {
            "Drafting/Execution": 1
        },
        "Execution of documents": {
            "Execution": 1
        }
    }
    
    return dict(departments=departments, category_data=category_data)

@app.route('/')
def dashboard():
    page = request.args.get('page', 1, type=int)
    tasks = Tasks.query.order_by(Tasks.Date_Created.desc()).paginate(
        page=page, per_page=app.config['TASKS_PER_PAGE'])
    return render_template('dashboard.html', tasks=tasks)

@app.route('/task/new', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        # Get form data
        dept_name = request.form.get('department')
        category = request.form.get('category')
        sub_category = request.form.get('sub_category')
        description = request.form.get('description')
        estimated_time = float(request.form.get('estimated_time'))
        user_name = request.form.get('user')
        time_spent = float(request.form.get('time_spent'))
        
        # Generate Display_id
        display_id = generate_display_id()
        
        # Create new task
        new_task = Tasks(
            Display_id=display_id,
            Dept_name=dept_name,
            Category=category,
            Sub_category=sub_category,
            Description=description,
            Estimated_time=estimated_time
        )
        
        db.session.add(new_task)
        db.session.flush()  # Flush to get the Task_id
        
        # Create initial log entry
        if time_spent > 0:
            log_entry = TaskLogs(
                Task_id=new_task.Task_id,
                User_name=user_name,
                time_taken=time_spent
            )
            db.session.add(log_entry)
        
        db.session.commit()
        flash('Task created successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('add_task.html')

@app.route('/task/<task_id>/add_time', methods=['POST'])
def add_time(task_id):
    user_name = request.form.get('user_name')
    time_taken = float(request.form.get('time_taken'))
    
    task = Tasks.query.get_or_404(task_id)
    
    log_entry = TaskLogs(
        Task_id=task.Task_id,
        User_name=user_name,
        time_taken=time_taken,
        log_date=datetime.utcnow()  # Explicitly set the date
    )
    
    db.session.add(log_entry)
    db.session.commit()
    
    # Update task modification date
    task.Date_Modified = datetime.utcnow()
    db.session.commit()
    
    flash('Time added successfully!', 'success')
    
    # Check where to redirect back to
    next_page = request.args.get('next')
    if next_page == 'detail':
        return redirect(url_for('task_detail', task_id=task_id))
    return redirect(url_for('dashboard'))

@app.route('/reports')
def reports():
    # Render the reports template with the chat interface
    return render_template('reports.html')


@app.route('/task/<task_id>')
def task_detail(task_id):
    task = Tasks.query.get_or_404(task_id)
    
    # Get all logs for this task
    logs = TaskLogs.query.filter_by(Task_id=task_id).order_by(TaskLogs.log_date.desc()).all()
    
    # Calculate total time spent
    total_time_spent = db.session.query(func.sum(TaskLogs.time_taken))\
                         .filter(TaskLogs.Task_id == task_id).scalar() or 0
    
    return render_template('task_detail.html', 
                          task=task, 
                          logs=logs, 
                          total_time_spent=total_time_spent)

if __name__ == '__main__':
    app.run(debug=True) 