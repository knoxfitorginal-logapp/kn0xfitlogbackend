from flask import Blueprint, request, jsonify
from src.models.user import db, ConsistencyRecord, Upload, User
from src.routes.auth import token_required
from datetime import datetime, date, timedelta
import random

consistency_bp = Blueprint('consistency', __name__)

def get_motivational_message(streak=0, missed_days=0):
    """Generate motivational messages based on user's progress"""
    
    if missed_days > 0:
        missed_messages = [
            "Don't let yesterday's miss define today's success! 💪",
            "Every champion has setbacks. What matters is the comeback! 🔥",
            "Your journey continues today. Let's get back on track! 🚀",
            "One missed day doesn't erase your progress. Keep going! ⚡",
            "The best time to restart is now. You've got this! 🌟",
            "Consistency isn't perfection. It's persistence! 💯",
            "Your future self is counting on today's effort! 🎯",
            "Small steps today, big results tomorrow! 📈",
            "Turn today's motivation into tomorrow's habit! ✨",
            "Progress over perfection, always! 🙌"
        ]
        return random.choice(missed_messages)
    
    if streak == 0:
        return "Ready to start your fitness journey? Every expert was once a beginner! 🚀"
    elif streak == 1:
        return "Great start! Day 1 is complete. Momentum is building! 🔥"
    elif streak < 7:
        return f"Amazing! {streak} days strong! You're building an incredible habit! 💪"
    elif streak < 14:
        return f"Fantastic {streak}-day streak! You're in the zone! 🌟"
    elif streak < 21:
        return f"Outstanding {streak} days! You're forming a powerful habit! ⚡"
    elif streak < 30:
        return f"Incredible {streak}-day streak! You're a consistency champion! 🏆"
    else:
        return f"Legendary {streak}-day streak! You're an inspiration! 👑"

def calculate_streak(user_id):
    """Calculate current streak for a user"""
    today = date.today()
    current_streak = 0
    
    # Start from yesterday and count backwards
    check_date = today - timedelta(days=1)
    
    while True:
        record = ConsistencyRecord.query.filter_by(
            user_id=user_id,
            date=check_date
        ).first()
        
        if record and (record.workout_logged or record.diet_logged):
            current_streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    
    return current_streak

def get_or_create_consistency_record(user_id, target_date):
    """Get or create consistency record for a specific date"""
    record = ConsistencyRecord.query.filter_by(
        user_id=user_id,
        date=target_date
    ).first()
    
    if not record:
        # Check if we need to start a new 30-day cycle
        latest_record = ConsistencyRecord.query.filter_by(
            user_id=user_id
        ).order_by(ConsistencyRecord.date.desc()).first()
        
        cycle_start = target_date
        if latest_record and latest_record.cycle_start:
            # Check if we're still within the 30-day cycle
            days_since_cycle_start = (target_date - latest_record.cycle_start).days
            if days_since_cycle_start < 30:
                cycle_start = latest_record.cycle_start
        
        record = ConsistencyRecord(
            user_id=user_id,
            date=target_date,
            cycle_start=cycle_start
        )
        db.session.add(record)
    
    return record

@consistency_bp.route('/data', methods=['GET'])
@token_required
def get_consistency_data(current_user):
    """Get consistency data for the current user"""
    try:
        # Get date range (default to last 30 days)
        end_date = date.today()
        start_date = end_date - timedelta(days=29)
        
        # Get consistency records
        records = ConsistencyRecord.query.filter(
            ConsistencyRecord.user_id == current_user.id,
            ConsistencyRecord.date >= start_date,
            ConsistencyRecord.date <= end_date
        ).order_by(ConsistencyRecord.date.asc()).all()
        
        # Calculate current streak
        current_streak = calculate_streak(current_user.id)
        
        # Get current cycle info
        latest_record = ConsistencyRecord.query.filter_by(
            user_id=current_user.id
        ).order_by(ConsistencyRecord.date.desc()).first()
        
        cycle_start = None
        cycle_day = 0
        if latest_record and latest_record.cycle_start:
            cycle_start = latest_record.cycle_start
            cycle_day = (end_date - cycle_start).days + 1
            if cycle_day > 30:
                cycle_day = 30
        
        # Calculate statistics
        total_days = len(records)
        workout_days = len([r for r in records if r.workout_logged])
        diet_days = len([r for r in records if r.diet_logged])
        both_logged_days = len([r for r in records if r.workout_logged and r.diet_logged])
        
        # Check if today's log is complete
        today_record = ConsistencyRecord.query.filter_by(
            user_id=current_user.id,
            date=end_date
        ).first()
        
        today_status = {
            'workout_logged': today_record.workout_logged if today_record else False,
            'diet_logged': today_record.diet_logged if today_record else False,
            'both_complete': (today_record.workout_logged and today_record.diet_logged) if today_record else False
        }
        
        return jsonify({
            'records': [record.to_dict() for record in records],
            'statistics': {
                'current_streak': current_streak,
                'total_days': total_days,
                'workout_days': workout_days,
                'diet_days': diet_days,
                'both_logged_days': both_logged_days,
                'workout_percentage': round((workout_days / total_days * 100) if total_days > 0 else 0, 1),
                'diet_percentage': round((diet_days / total_days * 100) if total_days > 0 else 0, 1),
                'completion_percentage': round((both_logged_days / total_days * 100) if total_days > 0 else 0, 1)
            },
            'cycle_info': {
                'cycle_start': cycle_start.isoformat() if cycle_start else None,
                'cycle_day': cycle_day,
                'days_remaining': max(0, 30 - cycle_day) if cycle_day > 0 else 30
            },
            'today_status': today_status,
            'motivational_message': get_motivational_message(current_streak)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch consistency data: {str(e)}'}), 500

@consistency_bp.route('/update', methods=['POST'])
@token_required
def update_consistency(current_user):
    """Update consistency record when user uploads"""
    try:
        data = request.get_json()
        target_date = data.get('date')
        upload_type = data.get('type')  # 'workout' or 'diet'
        
        if not target_date or not upload_type:
            return jsonify({'error': 'Date and type are required'}), 400
        
        if upload_type not in ['workout', 'diet']:
            return jsonify({'error': 'Type must be "workout" or "diet"'}), 400
        
        # Parse date
        try:
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Get or create consistency record
        record = get_or_create_consistency_record(current_user.id, target_date)
        
        # Update the appropriate field
        if upload_type == 'workout':
            record.workout_logged = True
        else:
            record.diet_logged = True
        
        # Calculate streak
        record.streak_day = calculate_streak(current_user.id)
        
        db.session.commit()
        
        # Check if both workout and diet are logged for today
        both_complete = record.workout_logged and record.diet_logged
        
        return jsonify({
            'message': f'{upload_type.title()} logged successfully',
            'record': record.to_dict(),
            'both_complete': both_complete,
            'motivational_message': get_motivational_message(record.streak_day)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update consistency: {str(e)}'}), 500

@consistency_bp.route('/streak', methods=['GET'])
@token_required
def get_streak(current_user):
    """Get current streak information"""
    try:
        current_streak = calculate_streak(current_user.id)
        
        # Get best streak
        best_streak = 0
        records = ConsistencyRecord.query.filter_by(
            user_id=current_user.id
        ).order_by(ConsistencyRecord.date.asc()).all()
        
        temp_streak = 0
        for i, record in enumerate(records):
            if record.workout_logged or record.diet_logged:
                temp_streak += 1
                best_streak = max(best_streak, temp_streak)
            else:
                temp_streak = 0
        
        # Check if user missed today
        today = date.today()
        today_record = ConsistencyRecord.query.filter_by(
            user_id=current_user.id,
            date=today
        ).first()
        
        missed_today = not (today_record and (today_record.workout_logged or today_record.diet_logged))
        
        return jsonify({
            'current_streak': current_streak,
            'best_streak': best_streak,
            'missed_today': missed_today,
            'motivational_message': get_motivational_message(current_streak, 1 if missed_today else 0)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch streak: {str(e)}'}), 500

@consistency_bp.route('/reset-cycle', methods=['POST'])
@token_required
def reset_cycle(current_user):
    """Reset the 30-day cycle"""
    try:
        today = date.today()
        
        # Create new cycle start record
        record = get_or_create_consistency_record(current_user.id, today)
        record.cycle_start = today
        
        db.session.commit()
        
        return jsonify({
            'message': 'New 30-day cycle started',
            'cycle_start': today.isoformat(),
            'motivational_message': 'Fresh start! Let\'s make these 30 days count! 🚀'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to reset cycle: {str(e)}'}), 500

@consistency_bp.route('/check-missed', methods=['GET'])
@token_required
def check_missed_entries(current_user):
    """Check for missed entries and return notification message"""
    try:
        today = date.today()
        current_time = datetime.now().time()
        
        # Check if it's after 8 PM (20:00)
        cutoff_time = datetime.strptime('20:00', '%H:%M').time()
        
        if current_time < cutoff_time:
            return jsonify({
                'should_notify': False,
                'message': 'Still time to log your progress today!'
            }), 200
        
        # Check today's record
        today_record = ConsistencyRecord.query.filter_by(
            user_id=current_user.id,
            date=today
        ).first()
        
        missed_workout = not (today_record and today_record.workout_logged)
        missed_diet = not (today_record and today_record.diet_logged)
        
        if missed_workout or missed_diet:
            missed_items = []
            if missed_workout:
                missed_items.append('workout')
            if missed_diet:
                missed_items.append('diet')
            
            current_streak = calculate_streak(current_user.id)
            
            notification_messages = [
                f"Don't break your {current_streak}-day streak! Log your {' and '.join(missed_items)} now! 💪",
                f"Your fitness journey needs you! Missing: {', '.join(missed_items)}. There's still time! 🔥",
                f"Champions log their progress daily! Don't forget your {' and '.join(missed_items)}! 🏆",
                f"Consistency is key! You haven't logged your {' and '.join(missed_items)} today. 📈",
                f"Your future self will thank you! Log your {' and '.join(missed_items)} before bed! ✨"
            ]
            
            return jsonify({
                'should_notify': True,
                'missed_items': missed_items,
                'message': random.choice(notification_messages),
                'current_streak': current_streak
            }), 200
        
        return jsonify({
            'should_notify': False,
            'message': 'Great job! All entries logged for today! 🎉'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to check missed entries: {str(e)}'}), 500

@consistency_bp.route('/weekly-summary', methods=['GET'])
@token_required
def get_weekly_summary(current_user):
    """Get weekly consistency summary"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=6)  # Last 7 days
        
        records = ConsistencyRecord.query.filter(
            ConsistencyRecord.user_id == current_user.id,
            ConsistencyRecord.date >= start_date,
            ConsistencyRecord.date <= end_date
        ).order_by(ConsistencyRecord.date.asc()).all()
        
        # Create daily summary
        daily_summary = []
        for i in range(7):
            check_date = start_date + timedelta(days=i)
            record = next((r for r in records if r.date == check_date), None)
            
            daily_summary.append({
                'date': check_date.isoformat(),
                'day_name': check_date.strftime('%A'),
                'workout_logged': record.workout_logged if record else False,
                'diet_logged': record.diet_logged if record else False,
                'both_complete': (record.workout_logged and record.diet_logged) if record else False
            })
        
        # Calculate weekly stats
        workout_days = len([d for d in daily_summary if d['workout_logged']])
        diet_days = len([d for d in daily_summary if d['diet_logged']])
        complete_days = len([d for d in daily_summary if d['both_complete']])
        
        return jsonify({
            'daily_summary': daily_summary,
            'weekly_stats': {
                'workout_days': workout_days,
                'diet_days': diet_days,
                'complete_days': complete_days,
                'workout_percentage': round((workout_days / 7 * 100), 1),
                'diet_percentage': round((diet_days / 7 * 100), 1),
                'completion_percentage': round((complete_days / 7 * 100), 1)
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch weekly summary: {str(e)}'}), 500

