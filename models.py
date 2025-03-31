from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class Tasks(db.Model):
    __tablename__ = 'tasks'
    
    Task_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    Display_id = db.Column(db.String(12), unique=True, nullable=False)
    Dept_name = db.Column(db.String(100), nullable=False)
    Category = db.Column(db.String(100), nullable=False)
    Sub_category = db.Column(db.String(100), nullable=False)
    Date_Created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    Description = db.Column(db.String(500), nullable=False)
    Date_Modified = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    Estimated_time = db.Column(db.Float, nullable=False)
    
    logs = db.relationship('TaskLogs', backref='task', lazy=True)
    
    def __repr__(self):
        return f'<Task {self.Display_id}>'

class TaskLogs(db.Model):
    __tablename__ = 'task_logs'
    
    Log_id = db.Column(db.Integer, primary_key=True)
    Task_id = db.Column(db.String(36), db.ForeignKey('tasks.Task_id'), nullable=False)
    User_name = db.Column(db.String(100), nullable=False)
    time_taken = db.Column(db.Float, nullable=False)
    log_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TaskLog {self.Log_id}>' 