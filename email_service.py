import os
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, TemplateId, Substitution, DynamicTemplateData

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails using SendGrid"""
    
    def __init__(self):
        self.api_key = os.environ.get('SENDGRID_API_KEY')
        if not self.api_key:
            logger.warning("SENDGRID_API_KEY environment variable not set. Email functionality disabled.")
            self.enabled = False
        else:
            self.enabled = True
            self.client = SendGridAPIClient(self.api_key)
            self.from_email = Email("noreply@quizgrader.app", "Quiz Grader App")
    
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
        if not self.enabled:
            logger.warning("Email service disabled. Cannot send email to %s", to_email)
            return False
        
        # Create message
        message = Mail(
            from_email=self.from_email,
            to_emails=To(to_email),
            subject=subject
        )
        
        # Add content
        if html_content:
            message.content = Content("text/html", html_content)
        elif text_content:
            message.content = Content("text/plain", text_content)
        else:
            logger.error("No content provided for email")
            return False
        
        try:
            # Send message
            response = self.client.send(message)
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email: {response.status_code} - {response.body}")
                return False
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
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
        subject = "Welcome to Quiz Grader App"
        html_content = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #4a86e8;">Welcome to Quiz Grader App!</h2>
                <p>Hi {username},</p>
                <p>Thank you for registering with Quiz Grader App. Your account has been successfully created.</p>
                <p>With Quiz Grader App, you can:</p>
                <ul>
                    <li>Upload handwritten quiz images</li>
                    <li>Extract text content using advanced AI</li>
                    <li>Grade student answers against standard references</li>
                    <li>Track student performance over time</li>
                </ul>
                <p>If you have any questions or need assistance, please don't hesitate to contact us.</p>
                <p>Best regards,<br>The Quiz Grader Team</p>
            </div>
        </body>
        </html>
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
        subject = "Password Reset - Quiz Grader App"
        reset_link = f"{reset_url}?token={reset_token}"
        
        html_content = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #4a86e8;">Password Reset Request</h2>
                <p>Hi {username},</p>
                <p>We received a request to reset your password for your Quiz Grader App account.</p>
                <p>To reset your password, please click the button below:</p>
                <p style="text-align: center;">
                    <a href="{reset_link}" 
                       style="background-color: #4a86e8; color: white; padding: 10px 20px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        Reset Password
                    </a>
                </p>
                <p>Or copy and paste this URL into your browser:</p>
                <p>{reset_link}</p>
                <p>This link will expire in 24 hours.</p>
                <p>If you did not request a password reset, please ignore this email or contact us if you have concerns.</p>
                <p>Best regards,<br>The Quiz Grader Team</p>
            </div>
        </body>
        </html>
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
        subject = f"Quiz Graded: {quiz_info.get('title', 'Standard Quiz')}"
        
        html_content = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #4a86e8;">Quiz Grading Complete</h2>
                <p>Hi {username},</p>
                <p>A quiz has been processed and graded successfully:</p>
                <ul>
                    <li><strong>Quiz:</strong> {quiz_info.get('title', 'Standard Quiz')}</li>
                    <li><strong>Student:</strong> {quiz_info.get('student_name', 'Unknown')}</li>
                    <li><strong>Standard:</strong> {quiz_info.get('standard_id', 'Unknown')}</li>
                    <li><strong>Total Mark:</strong> {quiz_info.get('total_mark', '0')}</li>
                    <li><strong>Submission Date:</strong> {quiz_info.get('submission_date', 'Unknown')}</li>
                </ul>
                <p style="text-align: center;">
                    <a href="{quiz_url}" 
                       style="background-color: #4a86e8; color: white; padding: 10px 20px; 
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        View Detailed Results
                    </a>
                </p>
                <p>Thank you for using Quiz Grader App!</p>
                <p>Best regards,<br>The Quiz Grader Team</p>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content=html_content)

# Create a singleton instance
email_service = EmailService()