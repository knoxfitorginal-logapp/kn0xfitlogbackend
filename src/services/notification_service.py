import schedule
import time
import threading
from datetime import datetime, date, timedelta
from src.models.user import db, User, ConsistencyRecord
import random
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.running = False
        self.thread = None
        
    def start(self):
        """Start the notification service"""
        if not self.running:
            self.running = True
            
            # Schedule daily check at 8 PM
            schedule.every().day.at("20:00").do(self.send_daily_reminders)
            
            # Schedule weekly motivation on Sunday at 9 AM
            schedule.every().sunday.at("09:00").do(self.send_weekly_motivation)
            
            # Start the scheduler thread
            self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.thread.start()
            
            logger.info("Notification service started")
    
    def stop(self):
        """Stop the notification service"""
        self.running = False
        schedule.clear()
        logger.info("Notification service stopped")
    
    def _run_scheduler(self):
        """Run the scheduler in a separate thread"""
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def send_daily_reminders(self):
        """Send daily reminder notifications to users who haven't logged"""
        try:
            logger.info("Checking for users who need daily reminders...")
            
            today = date.today()
            users = User.query.filter_by(is_active=True).all()
            
            for user in users:
                try:
                    # Check if user has logged today
                    today_record = ConsistencyRecord.query.filter_by(
                        user_id=user.id,
                        date=today
                    ).first()
                    
                    missed_workout = not (today_record and today_record.workout_logged)
                    missed_diet = not (today_record and today_record.diet_logged)
                    
                    if missed_workout or missed_diet:
                        self._send_reminder_notification(user, missed_workout, missed_diet)
                        
                except Exception as e:
                    logger.error(f"Error checking user {user.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in send_daily_reminders: {e}")
    
    def send_weekly_motivation(self):
        """Send weekly motivational messages"""
        try:
            logger.info("Sending weekly motivation messages...")
            
            users = User.query.filter_by(is_active=True).all()
            
            for user in users:
                try:
                    self._send_weekly_motivation_notification(user)
                except Exception as e:
                    logger.error(f"Error sending weekly motivation to user {user.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in send_weekly_motivation: {e}")
    
    def _send_reminder_notification(self, user, missed_workout, missed_diet):
        """Send reminder notification to a specific user"""
        try:
            missed_items = []
            if missed_workout:
                missed_items.append('workout')
            if missed_diet:
                missed_items.append('diet')
            
            # Calculate current streak
            current_streak = self._calculate_streak(user.id)
            
            # Generate personalized message
            messages = [
                f"Hey {user.username}! Don't break your {current_streak}-day streak! 💪",
                f"{user.username}, your fitness journey needs you today! 🔥",
                f"Time to log your {' and '.join(missed_items)}, {user.username}! 📱",
                f"Champions like you don't skip days, {user.username}! 🏆",
                f"Your future self will thank you, {user.username}! ⚡",
                f"Consistency is your superpower, {user.username}! 🌟",
                f"Just a quick reminder, {user.username} - log your progress! 📈",
                f"You're doing amazing, {user.username}! Don't stop now! 💯"
            ]
            
            message = random.choice(messages)
            
            # In a real implementation, this would send push notifications,
            # emails, or SMS. For now, we'll log it.
            logger.info(f"NOTIFICATION for {user.email}: {message}")
            
            # Store notification in database for later retrieval
            self._store_notification(user.id, message, 'daily_reminder')
            
        except Exception as e:
            logger.error(f"Error sending reminder to user {user.id}: {e}")
    
    def _send_weekly_motivation_notification(self, user):
        """Send weekly motivational message"""
        try:
            # Get weekly stats
            end_date = date.today()
            start_date = end_date - timedelta(days=6)
            
            records = ConsistencyRecord.query.filter(
                ConsistencyRecord.user_id == user.id,
                ConsistencyRecord.date >= start_date,
                ConsistencyRecord.date <= end_date
            ).all()
            
            complete_days = len([r for r in records if r.workout_logged and r.diet_logged])
            completion_rate = round((complete_days / 7 * 100), 1)
            
            # Generate motivational message based on performance
            if completion_rate >= 85:
                messages = [
                    f"Outstanding week, {user.username}! {completion_rate}% completion rate! 🏆",
                    f"You're on fire, {user.username}! {complete_days}/7 days completed! 🔥",
                    f"Incredible consistency, {user.username}! Keep it up! 🌟"
                ]
            elif completion_rate >= 60:
                messages = [
                    f"Great progress, {user.username}! {completion_rate}% this week! 💪",
                    f"You're building strong habits, {user.username}! 📈",
                    f"Solid week, {user.username}! Let's aim even higher! ⚡"
                ]
            else:
                messages = [
                    f"New week, fresh start, {user.username}! You've got this! 🚀",
                    f"Every expert was once a beginner, {user.username}! 💯",
                    f"This week is your comeback week, {user.username}! 🌟"
                ]
            
            message = random.choice(messages)
            
            logger.info(f"WEEKLY MOTIVATION for {user.email}: {message}")
            self._store_notification(user.id, message, 'weekly_motivation')
            
        except Exception as e:
            logger.error(f"Error sending weekly motivation to user {user.id}: {e}")
    
    def _calculate_streak(self, user_id):
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
    
    def _store_notification(self, user_id, message, notification_type):
        """Store notification in database for later retrieval"""
        try:
            # In a real implementation, you would have a Notification model
            # For now, we'll just log it
            logger.info(f"Stored notification for user {user_id}: {message}")
        except Exception as e:
            logger.error(f"Error storing notification: {e}")
    
    def send_achievement_notification(self, user_id, achievement_type, details):
        """Send achievement notification"""
        try:
            user = User.query.get(user_id)
            if not user:
                return
            
            achievement_messages = {
                'first_upload': f"Welcome to KN0X-FIT, {user.username}! Your journey begins now! 🚀",
                'streak_7': f"7-day streak achieved, {user.username}! You're building momentum! 🔥",
                'streak_14': f"2 weeks strong, {user.username}! Habits are forming! 💪",
                'streak_21': f"21 days! You're officially building a habit, {user.username}! 🌟",
                'streak_30': f"30-day milestone reached, {user.username}! You're unstoppable! 🏆",
                'cycle_complete': f"30-day cycle completed, {user.username}! Ready for the next challenge? 👑",
                'perfect_week': f"Perfect week completed, {user.username}! All workouts and meals logged! ⭐",
                'comeback': f"Welcome back, {user.username}! Every comeback starts with a single step! 💯"
            }
            
            message = achievement_messages.get(achievement_type, f"Great achievement, {user.username}!")
            
            logger.info(f"ACHIEVEMENT NOTIFICATION for {user.email}: {message}")
            self._store_notification(user_id, message, 'achievement')
            
        except Exception as e:
            logger.error(f"Error sending achievement notification: {e}")

# Global notification service instance
notification_service = NotificationService()

def start_notification_service():
    """Start the notification service"""
    notification_service.start()

def stop_notification_service():
    """Stop the notification service"""
    notification_service.stop()

def send_achievement_notification(user_id, achievement_type, details=None):
    """Send achievement notification"""
    notification_service.send_achievement_notification(user_id, achievement_type, details)

