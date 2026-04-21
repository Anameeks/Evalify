import math
from django.utils import timezone
from datetime import datetime, timedelta


def get_deadline_dt(assessment):
    if not assessment.due_date:
        return None
    return timezone.make_aware(
        datetime.combine(assessment.due_date,
                         datetime.max.time().replace(second=59, microsecond=0))
    )


def get_grace_deadline(assessment):
    deadline = get_deadline_dt(assessment)
    if deadline is None:
        return None
    return deadline + timedelta(hours=assessment.grace_period_hours)


def check_submission_window(assessment):
    now      = timezone.now()
    deadline = get_deadline_dt(assessment)

    if deadline is None:
        return {'can_submit': True, 'is_late': False, 'hours_late': 0,
                'window_msg': 'No deadline set.'}

    if now <= deadline:
        remaining = deadline - now
        h = int(remaining.total_seconds() // 3600)
        m = int((remaining.total_seconds() % 3600) // 60)
        return {'can_submit': True, 'is_late': False, 'hours_late': 0,
                'window_msg': f"Due in {h}h {m}m"}

    hours_late = (now - deadline).total_seconds() / 3600
    days_late  = hours_late / 24
    grace_end  = get_grace_deadline(assessment)

    # Within grace period
    if assessment.grace_period_hours > 0 and grace_end and now <= grace_end:
        gr = grace_end - now
        gh = int(gr.total_seconds() // 3600)
        gm = int((gr.total_seconds() % 3600) // 60)
        return {'can_submit': True, 'is_late': True,
                'hours_late': round(hours_late, 2),
                'window_msg': f"Grace period — {gh}h {gm}m left (deduction applies)"}

    # max_late_days window
    if assessment.max_late_days > 0:
        if days_late <= assessment.max_late_days:
            return {'can_submit': True, 'is_late': True,
                    'hours_late': round(hours_late, 2),
                    'window_msg': f"Late — {days_late:.1f} day(s) (deduction applies)"}
        return {'can_submit': False, 'is_late': True,
                'hours_late': round(hours_late, 2),
                'window_msg': f"Closed — {days_late:.1f} days late (max {assessment.max_late_days})"}

    return {'can_submit': False, 'is_late': True,
            'hours_late': round(hours_late, 2),
            'window_msg': "Deadline passed — submission closed."}


def calculate_deduction(assessment, hours_late):
    if hours_late <= 0 or assessment.late_deduction_value <= 0:
        return 0.0
    hours_after_grace = max(0.0, hours_late - assessment.grace_period_hours)
    if hours_after_grace <= 0:
        return 0.0
    days = math.ceil(hours_after_grace / 24)
    if assessment.max_late_days > 0:
        days = min(days, assessment.max_late_days)
    if assessment.late_deduction_type == 'percent':
        d = (assessment.late_deduction_value / 100) * assessment.total_marks * days
    else:
        d = assessment.late_deduction_value * days
    return round(min(d, float(assessment.total_marks)), 2)


def apply_late_deduction(submission):
    window = check_submission_window(submission.assessment)
    submission.is_late    = window['is_late']
    submission.hours_late = window['hours_late']
    submission.late_deduction = (
        calculate_deduction(submission.assessment, window['hours_late'])
        if window['is_late'] else 0.0
    )
    submission.final_score = max(0.0, submission.total_score - submission.late_deduction)
    submission.save(update_fields=['is_late', 'hours_late', 'late_deduction', 'final_score'])


def recalculate_final_score(submission):
    submission.final_score = max(0.0, submission.total_score - submission.late_deduction)
    submission.save(update_fields=['final_score'])