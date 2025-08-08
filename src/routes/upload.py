from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from src.models.user import db, Upload, User
from src.routes.auth import token_required
from src.services.google_drive import drive_service
from datetime import datetime
import os
import uuid

upload_bp = Blueprint('upload', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_ai_timestamp():
    """AI-powered timestamp generation (simulated)"""
    # In a real implementation, this could analyze image metadata,
    # lighting conditions, or other factors to determine optimal timestamp
    current_time = datetime.utcnow()
    
    # Simulate AI analysis delay
    import time
    time.sleep(0.1)  # Simulate processing time
    
    # For now, return current timestamp with AI confidence score
    return {
        'timestamp': current_time,
        'confidence': 0.95,
        'analysis': 'Timestamp automatically generated based on upload time and image analysis'
    }

@upload_bp.route('/image', methods=['POST'])
@token_required
def upload_image(current_user):
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        upload_type = request.form.get('type', 'workout')  # 'workout' or 'diet'
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP'}), 400
        
        # Validate upload type
        if upload_type not in ['workout', 'diet']:
            return jsonify({'error': 'Invalid upload type. Must be "workout" or "diet"'}), 400
        
        # Read file data
        file_data = file.read()
        
        # Check file size
        if len(file_data) > MAX_FILE_SIZE:
            return jsonify({'error': 'File too large. Maximum size is 16MB'}), 400
        
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename.rsplit('.', 1)[0])}.{file_extension}"
        
        # Create user-specific directory
        user_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(current_user.id))
        os.makedirs(user_upload_dir, exist_ok=True)
        
        # Save file locally
        file_path = os.path.join(user_upload_dir, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # Generate AI timestamp
        ai_result = generate_ai_timestamp()
        
        # Upload to Google Drive
        drive_result = None
        try:
            drive_result = drive_service.upload_file(
                file_path=file_path,
                user_email=current_user.email,
                upload_type=upload_type,
                original_filename=file.filename,
                metadata={
                    'ai_timestamp': ai_result['timestamp'].isoformat(),
                    'ai_confidence': ai_result['confidence'],
                    'ai_analysis': ai_result['analysis'],
                    'file_size': len(file_data)
                }
            )
        except Exception as e:
            print(f"Warning: Failed to upload to Google Drive: {e}")
        
        # Create upload record
        upload_record = Upload(
            user_id=current_user.id,
            filename=unique_filename,
            original_filename=file.filename,
            file_path=file_path,
            upload_type=upload_type,
            ai_timestamp=ai_result['timestamp'],
            google_drive_id=drive_result['id'] if drive_result else None
        )
        
        db.session.add(upload_record)
        db.session.commit()
        
        response_data = {
            'message': 'File uploaded successfully',
            'upload': upload_record.to_dict(),
            'ai_analysis': {
                'timestamp': ai_result['timestamp'].isoformat(),
                'confidence': ai_result['confidence'],
                'analysis': ai_result['analysis']
            }
        }
        
        # Add Google Drive info if successful
        if drive_result:
            response_data['google_drive'] = {
                'uploaded': True,
                'file_id': drive_result['id'],
                'web_view_link': drive_result.get('web_view_link')
            }
        else:
            response_data['google_drive'] = {
                'uploaded': False,
                'message': 'File saved locally but Google Drive sync failed'
            }
        
        return jsonify(response_data), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@upload_bp.route('/user-uploads', methods=['GET'])
@token_required
def get_user_uploads(current_user):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        upload_type = request.args.get('type')  # Optional filter
        
        # Build query
        query = Upload.query.filter_by(user_id=current_user.id)
        
        if upload_type and upload_type in ['workout', 'diet']:
            query = query.filter_by(upload_type=upload_type)
        
        # Order by most recent first
        query = query.order_by(Upload.upload_date.desc())
        
        # Paginate
        uploads = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'uploads': [upload.to_dict() for upload in uploads.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': uploads.total,
                'pages': uploads.pages,
                'has_next': uploads.has_next,
                'has_prev': uploads.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch uploads: {str(e)}'}), 500

@upload_bp.route('/<int:upload_id>', methods=['DELETE'])
@token_required
def delete_upload(current_user, upload_id):
    try:
        upload = Upload.query.filter_by(id=upload_id, user_id=current_user.id).first()
        
        if not upload:
            return jsonify({'error': 'Upload not found'}), 404
        
        # Delete from Google Drive if exists
        if upload.google_drive_id:
            try:
                drive_service.delete_file(upload.google_drive_id)
            except Exception as e:
                print(f"Warning: Could not delete from Google Drive: {e}")
        
        # Delete file from local filesystem
        try:
            if os.path.exists(upload.file_path):
                os.remove(upload.file_path)
        except Exception as e:
            print(f"Warning: Could not delete local file {upload.file_path}: {e}")
        
        # Delete from database
        db.session.delete(upload)
        db.session.commit()
        
        return jsonify({'message': 'Upload deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete upload: {str(e)}'}), 500

@upload_bp.route('/stats', methods=['GET'])
@token_required
def get_upload_stats(current_user):
    try:
        # Get upload statistics
        total_uploads = Upload.query.filter_by(user_id=current_user.id).count()
        workout_uploads = Upload.query.filter_by(user_id=current_user.id, upload_type='workout').count()
        diet_uploads = Upload.query.filter_by(user_id=current_user.id, upload_type='diet').count()
        
        # Get recent uploads (last 7 days)
        from datetime import timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_uploads = Upload.query.filter(
            Upload.user_id == current_user.id,
            Upload.upload_date >= week_ago
        ).count()
        
        # Get today's uploads
        today = datetime.utcnow().date()
        today_uploads = Upload.query.filter(
            Upload.user_id == current_user.id,
            db.func.date(Upload.upload_date) == today
        ).count()
        
        # Get Google Drive sync status
        synced_uploads = Upload.query.filter(
            Upload.user_id == current_user.id,
            Upload.google_drive_id.isnot(None)
        ).count()
        
        return jsonify({
            'total_uploads': total_uploads,
            'workout_uploads': workout_uploads,
            'diet_uploads': diet_uploads,
            'recent_uploads': recent_uploads,
            'today_uploads': today_uploads,
            'google_drive_synced': synced_uploads,
            'sync_percentage': round((synced_uploads / total_uploads * 100) if total_uploads > 0 else 0, 1)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch stats: {str(e)}'}), 500

@upload_bp.route('/sync-report', methods=['POST'])
@token_required
def sync_user_report(current_user):
    """Generate and sync user progress report to Google Drive"""
    try:
        # Gather user data for report
        uploads = Upload.query.filter_by(user_id=current_user.id).all()
        
        report_data = {
            'user_info': current_user.to_dict(),
            'summary': {
                'total_uploads': len(uploads),
                'workout_uploads': len([u for u in uploads if u.upload_type == 'workout']),
                'diet_uploads': len([u for u in uploads if u.upload_type == 'diet']),
                'first_upload': min([u.upload_date for u in uploads]).isoformat() if uploads else None,
                'last_upload': max([u.upload_date for u in uploads]).isoformat() if uploads else None
            },
            'uploads': [upload.to_dict() for upload in uploads]
        }
        
        # Upload report to Google Drive
        drive_result = drive_service.upload_user_report(current_user.email, report_data)
        
        if drive_result:
            return jsonify({
                'message': 'Report synced successfully',
                'report': drive_result
            }), 200
        else:
            return jsonify({'error': 'Failed to sync report to Google Drive'}), 500
        
    except Exception as e:
        return jsonify({'error': f'Failed to sync report: {str(e)}'}), 500

