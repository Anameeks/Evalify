
import re
from django.core.exceptions import ValidationError

def validate_student_email(value):
    
    pattern = r'^\d+@uap-bd\.edu$'
    if not re.match(pattern, value):
        raise ValidationError('Student email must be followed by @uap-bd.edu (e.g., 23101221@uap-bd.edu)')

def validate_faculty_email(value):
  
    pattern = r'^[A-Za-z][A-Za-z0-9._]*@uap-bd\.edu$'
    if not re.match(pattern, value):
        raise ValidationError('Faculty email  @uap-bd.edu')