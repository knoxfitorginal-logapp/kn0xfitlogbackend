from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship with uploads
    uploads = db.relationship('Upload', backref='user', lazy=True)
    consistency_records = db.relationship('ConsistencyRecord', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }

class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    upload_type = db.Column(db.String(50), nullable=False)  # 'workout' or 'diet'
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    ai_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    google_drive_id = db.Column(db.String(255))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'upload_type': self.upload_type,
            'upload_date': self.upload_date.isoformat() if self.upload_date else None,
            'ai_timestamp': self.ai_timestamp.isoformat() if self.ai_timestamp else None,
            'google_drive_id': self.google_drive_id
        }

class ConsistencyRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    workout_logged = db.Column(db.Boolean, default=False)
    diet_logged = db.Column(db.Boolean, default=False)
    streak_day = db.Column(db.Integer, default=0)
    cycle_start = db.Column(db.Date)  # Start of 30-day cycle
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'date': self.date.isoformat() if self.date else None,
            'workout_logged': self.workout_logged,
            'diet_logged': self.diet_logged,
            'streak_day': self.streak_day,
            'cycle_start': self.cycle_start.isoformat() if self.cycle_start else None
        }
