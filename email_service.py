import os
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

class EmailService:
    """Service for sending emails using SendGrid"""
    
    def __init__(self):
        """Initialize email service with SendGrid API key from environment"""
        self.api_key = os.environ.get('SENDGRID_API_KEY')
        # Use a generic verified sender email that's been verified in SendGrid
        self.from_email = 'hello@benlattimore.com'  # Using the same email as the test user
        
        # Check if API key is set
        if not self.api_key:
            logging.warning("SENDGRID_API_KEY not set. Email functionality will not work.")
        else:
            logging.info("Email service initialized with SendGrid")
    
    def send_email(self, to_email, subject, text_content=None, html_content=None):
        """
        Send a basic email
        
        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            text_content (str, optional): Plain text content
            html_content (str, optional): HTML content
        
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.api_key:
            logging.error("Cannot send email: SENDGRID_API_KEY not set")
            return False
        
        if not html_content and not text_content:
            logging.error("Cannot send email: No content provided")
            return False
        
        try:
            # Create SendGrid client
            sg = SendGridAPIClient(self.api_key)
            
            # Create message
            message = Mail(
                from_email=Email(self.from_email),
                to_emails=To(to_email),
                subject=subject
            )
            
            # Add content
            if html_content:
                message.content = Content("text/html", html_content)
            else:
                message.content = Content("text/plain", text_content)
            
            # Send email
            response = sg.send(message)
            
            # Log response
            status_code = response.status_code
            logging.info(f"Email sent to {to_email}, status code: {status_code}")
            
            return status_code >= 200 and status_code < 300
            
        except Exception as e:
            logging.error(f"Error sending email: {str(e)}")
            return False
    
    def send_welcome_email(self, to_email, username):
        """
        Send welcome email to new users
        
        Args:
            to_email (str): User's email address
            username (str): User's username
        
        Returns:
            bool: True if email was sent successfully
        """
        subject = "Welcome to Quiz Grader!"
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4a86e8;">Welcome to Quiz Grader!</h1>
            <p>Hello <strong>{username}</strong>,</p>
            <p>Thank you for registering with Quiz Grader. We're excited to have you on board!</p>
            <p>With Quiz Grader, you can:</p>
            <ul>
                <li>Upload handwritten student quiz papers</li>
                <li>Automatically extract and grade answers</li>
                <li>View comprehensive grading reports</li>
                <li>Track student performance over time</li>
            </ul>
            <p>If you have any questions or need assistance, please don't hesitate to contact us.</p>
            <p>Happy grading!</p>
            <p>The Quiz Grader Team</p>
        </div>
        """
        
        return self.send_email(to_email, subject, html_content=html_content)
    
    def send_password_reset_email(self, to_email, username, reset_token, reset_url):
        """
        Send password reset email
        
        Args:
            to_email (str): User's email address
            username (str): User's username
            reset_token (str): Password reset token
            reset_url (str): URL for password reset page
        
        Returns:
            bool: True if email was sent successfully
        """
        subject = "Password Reset Request - Quiz Grader"
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4a86e8;">Password Reset</h1>
            <p>Hello <strong>{username}</strong>,</p>
            <p>We received a request to reset your password for your Quiz Grader account. If you didn't make this request, you can safely ignore this email.</p>
            <p>To reset your password, click the button below or copy and paste the URL into your browser.</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" style="background-color: #4a86e8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">Reset Password</a>
            </p>
            <p style="font-size: 12px; color: #666;">{reset_url}</p>
            <p>This password reset link will expire in 24 hours.</p>
            <p>If you didn't request a password reset, please ignore this email or contact support if you have concerns.</p>
            <p>The Quiz Grader Team</p>
        </div>
        """
        
        return self.send_email(to_email, subject, html_content=html_content)
    
    def send_quiz_submission_notification(self, to_email, username, quiz_info, quiz_url):
        """
        Send notification when a quiz is submitted and graded
        
        Args:
            to_email (str): User's email address
            username (str): User's username
            quiz_info (dict): Information about the quiz
            quiz_url (str): URL to view the quiz results
        
        Returns:
            bool: True if email was sent successfully
        """
        subject = f"Quiz Graded: {quiz_info.get('title', 'New Quiz')}"
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4a86e8;">Quiz Grading Complete</h1>
            <p>Hello <strong>{username}</strong>,</p>
            <p>A quiz has been successfully graded in your Quiz Grader account.</p>
            <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Quiz Title:</strong> {quiz_info.get('title', 'N/A')}</p>
                <p><strong>Student:</strong> {quiz_info.get('student_name', 'N/A')}</p>
                <p><strong>Total Mark:</strong> {quiz_info.get('total_mark', 'N/A')}</p>
                <p><strong>Submission Date:</strong> {quiz_info.get('submission_date', 'N/A')}</p>
            </div>
            <p>To view the detailed results, click the button below:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{quiz_url}" style="background-color: #4a86e8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">View Quiz Results</a>
            </p>
            <p>The Quiz Grader Team</p>
        </div>
        """
        
        return self.send_email(to_email, subject, html_content=html_content)

# Create a singleton instance
email_service = EmailService()