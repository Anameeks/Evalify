from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count
from collections import defaultdict
import json
from .models import (User, Course, CLO, PLO, Assessment, Question,Enrollment, Submission, QuestionGrade, Announcement, StudyMaterial, Notification )
from .notifications import (notify_grade_released, notify_new_assignment, notify_new_material, notify_announcement)
from .grace_period import check_submission_window, apply_late_deduction, recalculate_final_score


#Home Redirect 
def home(request):
    if not request.user.is_authenticated:
        return render(request, 'homepage.html')
    if request.user.role == 'faculty' or request.user.is_superuser:
        return redirect('faculty_dashboard')
    elif request.user.role == 'student':
        return redirect('student_dashboard')
    elif request.user.role == 'admin':
        return redirect('faculty_dashboard')
    return render(request, 'homepage.html')


#Auth 

def sign_in_html(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
            if user and user.is_active:
                login(request, user)
                return redirect('home')
        except User.DoesNotExist:
            pass
        return render(request, 'sign_in.html', {'error': 'Invalid email or password.'})
    return render(request, 'sign_in.html')


def sign_up_html(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', 'student')

        # Basic validations
        if not full_name or not email or not password:
            return render(request, 'sign_up.html', {'error': 'All fields are required.'})
        if len(password) < 8:
            return render(request, 'sign_up.html', {'error': 'Password must be at least 8 characters.'})
        if User.objects.filter(email=email).exists():
            return render(request, 'sign_up.html', {'error': 'Email already registered.'})

        # --- EMAIL DOMAIN VALIDATION BASED ON ROLE ---
        import re
        if role == 'student':
            # Must be digits@uap-bd.edu
            if not re.match(r'^\d+@uap-bd\.edu$', email):
                return render(request, 'sign_up.html', {'error': 'Student email must be digits@uap-bd.edu (e.g., 20241001@uap-bd.edu).'})
        elif role == 'faculty':
            # Must be name (letters/dots/underscores)@uap-bd.edu
            if not re.match(r'^[A-Za-z][A-Za-z0-9._]*@uap-bd\.edu$', email):
                return render(request, 'sign_up.html', {'error': 'Faculty email must be name@uap-bd.edu (e.g., john.doe@uap-bd.edu).'})
        else:
            return render(request, 'sign_up.html', {'error': 'Invalid role selected.'})

        # Generate unique username from email local part
        username = email.split('@')[0]
        base = username
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{i}"
            i += 1

        # Create user (your custom User model has `role` and `full_name` fields)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            role=role,
        )
        login(request, user)
        return redirect('home')
    return render(request, 'sign_up.html')


def sign_out(request):
    logout(request)
    return redirect('sign_in_html')


# Faculty Required

def faculty_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('sign_in_html')
        if request.user.role not in ('faculty', 'admin') and not request.user.is_superuser:
            return redirect('student_dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# Student Required 

def student_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('sign_in_html')
        if request.user.role not in ('student', 'admin') and not request.user.is_superuser:
            return redirect('faculty_dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper



#Faculty Views

@faculty_required
def faculty_dashboard(request):
    courses = Course.objects.filter(faculty=request.user)
    assessments = Assessment.objects.filter(course__in=courses)
    pending_subs = Submission.objects.filter(assessment__in=assessments, status='submitted')
    flagged_subs = Submission.objects.filter(assessment__in=assessments, status='flagged')
    recent_submissions = Submission.objects.filter(
        assessment__in=assessments
    ).select_related('student', 'assessment').order_by('-submitted_at')[:8]
    announcements = Announcement.objects.filter(
        course__in=courses
    ).order_by('-created_at')[:5]

    return render(request, 'faculty/dashboard.html', {
        'courses': courses,
        'assessments_count': assessments.count(),
        'pending_count': pending_subs.count(),
        'flagged_count': flagged_subs.count(),
        'recent_submissions': recent_submissions,
        'announcements': announcements,
    })


@faculty_required
def faculty_courses(request):
    courses = Course.objects.filter(faculty=request.user).prefetch_related(
        'clos', 'clos__plos', 'enrollments', 'enrollments__student'
    )
    # PLO count per course calculate করা
    for course in courses:
        plo_ids = set()
        for clo in course.clos.all():
            for plo in clo.plos.all():
                plo_ids.add(plo.id)
        course.plo_count = len(plo_ids)
 
    plos = PLO.objects.all()
    return render(request, 'faculty/courses.html', {
        'courses': courses,
        'plos': plos,
    })
 


@faculty_required
def add_course(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        course = Course.objects.create(
            code=data['code'], name=data['name'],
            description=data.get('description', ''),
            credit_hours=int(data.get('credit_hours', 3)),
            semester=data.get('semester', 'Fall 2025'),
            faculty=request.user
        )
        return JsonResponse({'success': True, 'id': course.id})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def add_clo(request, course_id):
    course = get_object_or_404(Course, id=course_id, faculty=request.user)
    if request.method == 'POST':
        data = json.loads(request.body)
        count = course.clos.count() + 1
        clo = CLO.objects.create(
            course=course, code=f"CLO{count}",
            description=data['description'],
            bloom_level=data['bloom_level']
        )
        if data.get('plo_ids'):
            clo.plos.set(PLO.objects.filter(id__in=data['plo_ids']))
        return JsonResponse({'success': True, 'id': clo.id, 'code': clo.code})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def delete_clo(request, clo_id):
    clo = get_object_or_404(CLO, id=clo_id, course__faculty=request.user)
    clo.delete()
    return JsonResponse({'success': True})


@faculty_required
def get_course_clos(request, course_id):
    course = get_object_or_404(Course, id=course_id, faculty=request.user)
    clos = list(course.clos.values('id', 'code', 'description', 'bloom_level'))
    return JsonResponse({'clos': clos})


@faculty_required
def add_student_to_course(request, course_id):
    course = get_object_or_404(Course, id=course_id, faculty=request.user)
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            student = User.objects.get(email=data['email'], role='student')
            Enrollment.objects.get_or_create(student=student, course=course)
            return JsonResponse({'success': True, 'name': student.full_name or student.username})
        except User.DoesNotExist:
            return JsonResponse({'error': 'Student not found'}, status=404)
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def faculty_assessments(request):
    courses = Course.objects.filter(faculty=request.user)
    assessments = Assessment.objects.filter(course__in=courses).prefetch_related(
        'questions__clos__plos'
    ).order_by('-created_at')
    return render(request, 'faculty/assessments.html', {
        'assessments': assessments, 'courses': courses
    })


@faculty_required
def create_assessment(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        course = get_object_or_404(Course, id=data['course_id'], faculty=request.user)
        assessment = Assessment.objects.create(
            course=course, title=data['title'],
            description=data.get('description', ''),
            assessment_type=data['assessment_type'],
            due_date=data['due_date'], status='published'
        )
        total = 0
        for i, q in enumerate(data.get('questions', []), 1):
            question = Question.objects.create(
                assessment=assessment, order=i,
                text=q['text'], max_marks=int(q['max_marks'])
            )
            if q.get('clo_ids'):
                question.clos.set(CLO.objects.filter(id__in=q['clo_ids']))
            total += int(q['max_marks'])
        Assessment.objects.filter(pk=assessment.pk).update(total_marks=total)
        return JsonResponse({'success': True, 'id': assessment.id})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def faculty_grading(request):
    courses = Course.objects.filter(faculty=request.user)
    assessments = Assessment.objects.filter(course__in=courses)
    submissions = Submission.objects.filter(
        assessment__in=assessments
    ).select_related('student', 'assessment__course').order_by('-submitted_at')
    return render(request, 'faculty/grading.html', {
        'submissions': submissions,
        'assessments': assessments,
        'pending': submissions.filter(status='submitted').count(),
        'graded': submissions.filter(status='graded').count(),
        'flagged': submissions.filter(status='flagged').count(),
    })


@faculty_required
def get_submission_detail(request, sub_id):
    sub = get_object_or_404(Submission, id=sub_id, assessment__course__faculty=request.user)
    questions = []
    for q in sub.assessment.questions.all():
        try:
            obtained = QuestionGrade.objects.get(submission=sub, question=q).marks_obtained
        except QuestionGrade.DoesNotExist:
            obtained = 0
        questions.append({
            'id': q.id, 'order': q.order, 'text': q.text,
            'max_marks': q.max_marks, 'obtained': obtained,
            'clos': [{'code': c.code} for c in q.clos.all()],
            'plos': [{'code': p.code} for p in q.plos.all()],
        })
    file_url = sub.submitted_file.url if sub.submitted_file else None
    file_name = sub.submitted_file.name.split('/')[-1] if sub.submitted_file else None
    return JsonResponse({
        'id': sub.id,
        'student_name': sub.student.full_name or sub.student.username,
        'assessment_title': sub.assessment.title,
        'assessment_type': sub.assessment.assessment_type,
        'total_marks': sub.assessment.total_marks,
        'content': sub.content,
        'file_url': file_url,
        'file_name': file_name,
        'plagiarism': sub.plagiarism_score,
        'ai_content': sub.ai_content_score,
        'status': sub.status,
        'total_score': sub.total_score,
        'feedback': sub.feedback,
        'questions': questions,
    })


@faculty_required
def grade_submission(request, sub_id):
    sub = get_object_or_404(Submission, id=sub_id, assessment__course__faculty=request.user)
    if request.method == 'POST':
        data = json.loads(request.body)
        total = 0
        for qg_data in data.get('question_grades', []):
            q = get_object_or_404(Question, id=qg_data['question_id'])
            marks = min(float(qg_data['marks']), q.max_marks)
            QuestionGrade.objects.update_or_create(
                submission=sub, question=q, defaults={'marks_obtained': marks}
            )
            total += marks
 
        was_graded_before = sub.status in ('graded', 'flagged')  # ← নতুন
 
        status = 'flagged' if (sub.plagiarism_score > 30 or sub.ai_content_score > 50) else 'graded'
        sub.total_score = total
        sub.feedback    = data.get('feedback', '')
        sub.status      = status
        sub.save()

        recalculate_final_score(sub)

        if not was_graded_before:
            notify_grade_released(sub)
 
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def faculty_analytics(request):
    courses = Course.objects.filter(faculty=request.user)
    selected_course = None
    grade_dist = []
    clo_attainment = []
    weak_students = []
    integrity_data = {'clean': 0, 'ai_flag': 0, 'plagiarism': 0}
    student_clo_data = []
    plo_attainment = []

    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
    elif courses.exists():
        selected_course = courses.first()

    if selected_course:
        assessments = Assessment.objects.filter(course=selected_course)
        graded_subs = Submission.objects.filter(
            assessment__in=assessments, status__in=['graded', 'flagged']
        )
        ranges = [('90-100', 90, 100), ('80-89', 80, 89), ('70-79', 70, 79), ('60-69', 60, 69), ('<60', 0, 59)]
        for label, lo, hi in ranges:
            count = sum(
                1 for s in graded_subs
                if s.assessment.total_marks > 0
                and lo <= (s.total_score / s.assessment.total_marks * 100) <= hi
            )
            grade_dist.append({'label': label, 'count': count})

        for clo in selected_course.clos.all():
            q_ids = list(Question.objects.filter(assessment__in=assessments, clos=clo).values_list('id', flat=True))
            qgs = QuestionGrade.objects.filter(question_id__in=q_ids, submission__in=graded_subs)
            total_possible = sum(Question.objects.get(id=qid).max_marks for qid in q_ids) * max(graded_subs.count(), 1)
            total_obtained = sum(g.marks_obtained for g in qgs)
            attainment = round((total_obtained / total_possible * 100) if total_possible > 0 else 0, 1)
            clo_attainment.append({'code': clo.code, 'attainment': attainment})

        # Per-student average CLO attainment
        for enrollment in Enrollment.objects.filter(course=selected_course).select_related('student'):
            student = enrollment.student
            s_subs = graded_subs.filter(student=student)
            if not s_subs.exists():
                continue
            clo_atts = []
            for clo in selected_course.clos.all():
                q_ids = list(Question.objects.filter(assessment__in=assessments, clos=clo).values_list('id', flat=True))
                if not q_ids:
                    continue
                qgs = QuestionGrade.objects.filter(question_id__in=q_ids, submission__in=s_subs)
                tp = sum(Question.objects.get(id=qid).max_marks for qid in q_ids)
                to = sum(g.marks_obtained for g in qgs)
                if tp > 0:
                    clo_atts.append(to / tp * 100)
            if clo_atts:
                student_clo_data.append({
                    'name': (student.full_name or student.username)[:20],
                    'attainment': round(sum(clo_atts) / len(clo_atts), 1)
                })

        # PLO attainment aggregated across all graded submissions
        plo_agg = defaultdict(lambda: {'obtained': 0.0, 'total': 0.0, 'plo': None})
        for clo in selected_course.clos.all():
            q_ids = list(Question.objects.filter(assessment__in=assessments, clos=clo).values_list('id', flat=True))
            qgs = QuestionGrade.objects.filter(question_id__in=q_ids, submission__in=graded_subs)
            tp = sum(Question.objects.get(id=qid).max_marks for qid in q_ids) * max(graded_subs.count(), 1)
            to = sum(g.marks_obtained for g in qgs)
            for plo in clo.plos.all():
                if plo_agg[plo.id]['plo'] is None:
                    plo_agg[plo.id]['plo'] = plo
                plo_agg[plo.id]['obtained'] += to
                plo_agg[plo.id]['total'] += tp
        for pid, pd in plo_agg.items():
            p = pd['plo']
            att = round((pd['obtained'] / pd['total'] * 100) if pd['total'] > 0 else 0, 1)
            plo_attainment.append({'code': p.code, 'description': p.description, 'attainment': att})

        for sub in graded_subs:
            if sub.assessment.total_marks > 0:
                pct = round(sub.total_score / sub.assessment.total_marks * 100, 1)
                if pct < 70:
                    weak_students.append({
                        'name': sub.student.full_name or sub.student.username,
                        'score': f"{int(sub.total_score)}/{sub.assessment.total_marks}",
                        'pct': pct
                    })
            if sub.plagiarism_score > 30:
                integrity_data['plagiarism'] += 1
            elif sub.ai_content_score > 50:
                integrity_data['ai_flag'] += 1
            else:
                integrity_data['clean'] += 1

    return render(request, 'faculty/analytics.html', {
        'courses': courses,
        'selected_course': selected_course,
        'grade_dist': json.dumps(grade_dist),
        'clo_attainment': json.dumps(clo_attainment),
        'clo_attainment_list': clo_attainment,
        'weak_students': weak_students,
        'integrity_data': json.dumps(integrity_data),
        'student_clo_data': json.dumps(student_clo_data),
        'student_clo_list': student_clo_data,
        'plo_attainment': json.dumps(plo_attainment),
        'plo_attainment_list': plo_attainment,
    })


@faculty_required
def faculty_announcements(request):
    courses = Course.objects.filter(faculty=request.user)
    announcements = Announcement.objects.filter(
        course__in=courses
    ).select_related('course').order_by('-created_at')
    return render(request, 'faculty/announcements.html', {
        'announcements': announcements, 'courses': courses
    })


@faculty_required
def create_announcement(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        course = get_object_or_404(Course, id=data['course_id'], faculty=request.user)
        ann = Announcement.objects.create(
            course=course, title=data['title'], content=data['content'],
            priority=data.get('priority', 'medium'), created_by=request.user
        )
        notify_announcement(ann) 
        return JsonResponse({'success': True, 'id': ann.id})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def delete_announcement(request, ann_id):
    ann = get_object_or_404(Announcement, id=ann_id, created_by=request.user)
    ann.delete()
    return JsonResponse({'success': True})


# Student Views

@student_required
def student_dashboard(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    courses = [e.course for e in enrollments]
    assessments = Assessment.objects.filter(course__in=courses, status='published')
    submissions = Submission.objects.filter(student=request.user, assessment__in=assessments)
    submitted_ids = submissions.values_list('assessment_id', flat=True)
    pending_count = assessments.exclude(id__in=submitted_ids).count()
    graded = submissions.filter(status='graded')
    avg_grade = 0
    if graded.exists():
        total_pct = sum(
            (s.total_score / s.assessment.total_marks * 100)
            for s in graded if s.assessment.total_marks > 0
        )
        avg_grade = round(total_pct / graded.count(), 1)
    recent_grades = graded.select_related('assessment').order_by('-submitted_at')[:5]
    announcements = Announcement.objects.filter(course__in=courses).order_by('-created_at')[:5]
    return render(request, 'student/dashboard.html', {
        'courses': courses,
        'submissions_count': submissions.count(),
        'pending_count': pending_count,
        'avg_grade': avg_grade,
        'recent_grades': recent_grades,
        'announcements': announcements,
    })


@student_required
def student_courses(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    enrolled_ids = [e.course_id for e in enrollments]
    courses = []
    for e in enrollments:
        c = e.course
        c.clos_list = c.clos.prefetch_related('plos').all()
        c.assignment_count = Assessment.objects.filter(course=c, status='published').count()
        courses.append(c)
    all_courses = Course.objects.exclude(id__in=enrolled_ids)
    return render(request, 'student/courses.html', {
        'courses': courses, 'all_courses': all_courses
    })


@student_required
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    Enrollment.objects.get_or_create(student=request.user, course=course)
    return JsonResponse({'success': True})


@student_required
def student_submissions(request):
    enrollments = Enrollment.objects.filter(student=request.user)
    courses = [e.course for e in enrollments]
    assessments = Assessment.objects.filter(course__in=courses, status='published')
    submissions = Submission.objects.filter(
        student=request.user, assessment__in=assessments
    ).select_related('assessment__course').order_by('-submitted_at')
    submitted_ids = submissions.values_list('assessment_id', flat=True)
    pending_assessments = assessments.exclude(id__in=submitted_ids)
    return render(request, 'student/submissions.html', {
        'submissions': submissions,
        'pending_assessments': pending_assessments,
    })


@student_required
def submit_assessment(request, assessment_id):
    assessment = get_object_or_404(Assessment, id=assessment_id, status='published')
    if not Enrollment.objects.filter(student=request.user, course=assessment.course).exists():
        return JsonResponse({'error': 'Not enrolled'}, status=403)
    if request.method == 'POST':
        data = json.loads(request.body)
        content = data.get('content', '')
        sub, created = Submission.objects.get_or_create(
            student=request.user, assessment=assessment,
            defaults={
                'content': content,
                'plagiarism_score': round(len(content) % 50, 1),
                'ai_content_score': round(len(content) % 20, 1),
            }
        )
        if not created:
            return JsonResponse({'error': 'Already submitted'}, status=400)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=400)


@student_required
def student_clo_results(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    results = []
    for e in enrollments:
        course = e.course
        assessments = Assessment.objects.filter(course=course, status='published')
        subs = Submission.objects.filter(
            student=request.user, assessment__in=assessments,
            status__in=['graded', 'flagged']
        )
        avg_pct = 0
        if subs.exists():
            total = sum(
                (s.total_score / s.assessment.total_marks * 100)
                for s in subs if s.assessment.total_marks > 0
            )
            avg_pct = round(total / subs.count(), 1)
        grade = 'F'
        if avg_pct >= 80: grade = 'A+'
        elif avg_pct >= 75: grade = 'A'
        elif avg_pct >= 70: grade = 'A-'
        elif avg_pct >= 65: grade = 'B+'
        elif avg_pct >= 60: grade = 'B'
        elif avg_pct >= 55: grade = 'B-'
        elif avg_pct >= 50: grade = 'C+'
        elif avg_pct >= 45: grade = 'C'
        elif avg_pct >= 40: grade = 'D'

        clo_results = []
        plo_agg = defaultdict(lambda: {'obtained': 0.0, 'total': 0.0, 'plo': None})
        for clo in course.clos.all():
            q_ids = list(Question.objects.filter(assessment__in=assessments, clos=clo).values_list('id', flat=True))
            qgs = QuestionGrade.objects.filter(question_id__in=q_ids, submission__in=subs)
            total_possible = sum(Question.objects.get(id=qid).max_marks for qid in q_ids)
            total_obtained = sum(g.marks_obtained for g in qgs)
            attainment = round((total_obtained / total_possible * 100) if total_possible > 0 else 0, 1)
            clo_results.append({
                'code': clo.code, 'bloom': clo.bloom_level,
                'description': clo.description,
                'obtained': int(total_obtained), 'total': int(total_possible),
                'attainment': attainment
            })
            for plo in clo.plos.all():
                if plo_agg[plo.id]['plo'] is None:
                    plo_agg[plo.id]['plo'] = plo
                plo_agg[plo.id]['obtained'] += total_obtained
                plo_agg[plo.id]['total'] += total_possible

        plo_results = []
        for pid, data in plo_agg.items():
            plo = data['plo']
            att = round((data['obtained'] / data['total'] * 100) if data['total'] > 0 else 0, 1)
            plo_results.append({'code': plo.code, 'description': plo.description, 'attainment': att})

        results.append({
            'course': course, 'grade': grade,
            'avg_pct': avg_pct, 'graded_count': subs.count(),
            'clo_results': clo_results,
            'plo_results': plo_results,
        })
    return render(request, 'student/clo_results.html', {'results': results})


@student_required
def student_notifications(request):
    notifs      = Notification.objects.filter(
        recipient=request.user
    ).select_related('course', 'assessment')
    unread_count = notifs.filter(is_read=False).count()
    # mark all read when page opens
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, 'student/notifications.html', {
        'notifs':       notifs,
        'unread_count': unread_count,
    })



# Study Material Views 

@faculty_required
def faculty_materials(request):
    courses = Course.objects.filter(faculty=request.user)
 
    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
        materials = StudyMaterial.objects.filter(
            course=selected_course
        ).order_by('-uploaded_at')
        return render(request, 'faculty/materials.html', {
            'selected_course': selected_course,
            'courses': courses,
            'materials': materials,
            'material_count': materials.count(),
        })
 
    # Course list view — annotate counts
    for c in courses:
        c.material_count = StudyMaterial.objects.filter(course=c).count()
        c.visible_count  = StudyMaterial.objects.filter(course=c, is_visible=True).count()
        c.hidden_count   = StudyMaterial.objects.filter(course=c, is_visible=False).count()
 
    return render(request, 'faculty/materials.html', {
        'selected_course': None,
        'courses': courses,
    })


@faculty_required
def upload_material(request):
    if request.method == 'POST':
        course_id     = request.POST.get('course_id')
        title         = request.POST.get('title', '').strip()
        description   = request.POST.get('description', '').strip()
        material_type = request.POST.get('material_type', 'lecture_note')
        video_url     = request.POST.get('video_url', '').strip()
        uploaded_file = request.FILES.get('file')
 
        course = get_object_or_404(Course, id=course_id, faculty=request.user)
 
        # ── Permission check ──
        if not title:
            return JsonResponse({'error': 'Title is required.'}, status=400)
        if material_type == 'video' and not video_url and not uploaded_file:
            return JsonResponse({'error': 'Please provide a video URL or upload a video file.'}, status=400)
        if material_type != 'video' and not uploaded_file and not video_url:
            return JsonResponse({'error': 'Please select a file to upload.'}, status=400)
 
        material = StudyMaterial.objects.create(
            course=course,
            title=title,
            description=description,
            material_type=material_type,
            file=uploaded_file,
            video_url=video_url,
            uploaded_by=request.user,
            is_visible=True,
        )
        return JsonResponse({
            'success':       True,
            'id':            material.id,
            'title':         material.title,
            'description':   material.description,
            'material_type': material.material_type,
            'type_label':    material.get_material_type_display(),
            'file_url':      material.file.url if material.file else '',
            'filename':      material.filename(),
            'video_url':     material.video_url,
            'embed_url':     material.embed_url(),
            'is_video':      material.is_video(),
            'is_visible':    material.is_visible,
            'uploaded_at':   material.uploaded_at.strftime('%b %d, %Y'),
        })
    return JsonResponse({'error': 'POST required'}, status=400)

@faculty_required
def toggle_material_visibility(request, material_id):
    """Faculty can show/hide a material from students."""
    material = get_object_or_404(StudyMaterial, id=material_id, course__faculty=request.user)
    material.is_visible = not material.is_visible
    material.save()
    return JsonResponse({'success': True, 'is_visible': material.is_visible})


@faculty_required
def delete_material(request, material_id):
    material = get_object_or_404(StudyMaterial, id=material_id, course__faculty=request.user)
    if material.file:
        material.file.delete(save=False)
    material.delete()
    return JsonResponse({'success': True})


@student_required
def student_materials(request):
    enrollments = Enrollment.objects.filter(student=request.user)
    courses     = [e.course for e in enrollments]
 
    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=int(course_id))
 
        # Permission check — must be enrolled
        if selected_course not in courses:
            from django.shortcuts import redirect
            return redirect('student_materials')
 
        # Only show visible materials
        materials = StudyMaterial.objects.filter(
            course=selected_course,
            is_visible=True,         # ← students only see visible ones
        ).order_by('-uploaded_at')
 
        return render(request, 'student/materials.html', {
            'selected_course': selected_course,
            'materials':       materials,
            'material_count':  materials.count(),
        })
 
    # Course list
    for c in courses:
        c.material_count = StudyMaterial.objects.filter(course=c, is_visible=True).count()
 
    return render(request, 'student/materials.html', {
        'selected_course': None,
        'courses':         courses,
    })

@faculty_required
def add_plo(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        desc = data.get('description', '').strip()
        if not desc:
            return JsonResponse({'error': 'Description required'}, status=400)
        count = PLO.objects.count() + 1
        plo = PLO.objects.create(
            code=f"PLO{count}",
            description=desc,
            created_by=request.user
        )
        return JsonResponse({'success': True, 'id': plo.id, 'code': plo.code})
    return JsonResponse({'error': 'POST required'}, status=400)


# Faculty Assignment Views 

@faculty_required
def faculty_assignments(request):
    courses = Course.objects.filter(faculty=request.user)
    plos = PLO.objects.all()

    course_id = request.GET.get('course')
    if course_id:
        # Course detail view 
        selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
        base_qs = Assessment.objects.filter(course=selected_course).select_related('course').prefetch_related(
            'questions', 'questions__clos', 'questions__plos'
        )
        drafts = list(base_qs.filter(status='draft').order_by('-created_at'))
        published_list = list(base_qs.filter(status='published').order_by('-created_at'))
        for a in drafts + published_list:
            a.submission_count = a.submissions.count()
            a.question_count = a.questions.count()
        return render(request, 'faculty/assignments.html', {
            'selected_course': selected_course,
            'courses': courses,
            'drafts': drafts,
            'published_list': published_list,
            'plos': plos,
            'draft_count': len(drafts),
            'published_count': len(published_list),
            'total_subs': sum(a.submission_count for a in published_list),
        })

    # Course list view 
    for c in courses:
        c.total_count = Assessment.objects.filter(course=c).count()
        c.draft_count = Assessment.objects.filter(course=c, status='draft').count()
        c.published_count = Assessment.objects.filter(course=c, status='published').count()
    return render(request, 'faculty/assignments.html', {
        'selected_course': None,
        'courses': courses,
        'plos': plos,
    })


@faculty_required
def create_assignment(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        course = get_object_or_404(Course, id=data['course_id'], faculty=request.user)
        assessment_type = data.get('assessment_type', 'assignment')
        # Assignments publish immediately; all other types save as draft
        status = 'published' if assessment_type == 'assignment' else 'draft'
        # due_date is optional for non-assignment types
        due_date = data.get('due_date') or None
        assignment = Assessment.objects.create(
            course=course,
            title=data['title'],
            description=data.get('description', ''),
            assessment_type=assessment_type,
            due_date=due_date,
            status=status,
            total_marks=0,
            grace_period_hours   = int(data.get('grace_period_hours', 0)),
            late_deduction_type  = data.get('late_deduction_type', 'percent'),
            late_deduction_value = float(data.get('late_deduction_value', 0)),
            max_late_days        = int(data.get('max_late_days', 0)),
        )
        total = 0
        for i, q in enumerate(data.get('questions', []), 1):
            question = Question.objects.create(
                assessment=assignment,
                order=i,
                text=q['text'],
                max_marks=int(q.get('max_marks', 10)),
            )
            if q.get('clo_ids'):
                question.clos.set(CLO.objects.filter(id__in=q['clo_ids']))
            if q.get('plo_ids'):
                question.plos.set(PLO.objects.filter(id__in=q['plo_ids']))
            total += int(q.get('max_marks', 10))
        # Use manual total_marks if provided and no questions, else sum of questions
        manual_total = int(data.get('total_marks', 0))
        assignment.total_marks = total if total > 0 else manual_total

        if status == 'published':
            notify_new_assignment(assignment)

        type_labels = dict(Assessment.TYPE_CHOICES)
        return JsonResponse({
            'success': True,
            'id': assignment.id,
            'title': assignment.title,
            'type_label': type_labels.get(assessment_type, assessment_type),
            'assessment_type': assessment_type,
            'status': status,
            'course_name': f"{course.code}: {course.name}",
            'due_date': str(assignment.due_date),
            'total_marks': assignment.total_marks,
            'description': assignment.description,
            'question_count': len(data.get('questions', [])),
        })
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(
        Assessment, id=assignment_id, course__faculty=request.user
    )
    assignment.delete()
    return JsonResponse({'success': True})


@faculty_required
def publish_assessment(request, assignment_id):
    assessment = get_object_or_404(
        Assessment, id=assignment_id, course__faculty=request.user
    )
    assessment.status = 'published'
    assessment.save()
    notify_new_assignment(assessment)
 
    return JsonResponse({'success': True})


# Student Assignment Views 

@student_required
def student_assignments(request):
    enrollments = Enrollment.objects.filter(student=request.user)
    courses = [e.course for e in enrollments]
    assessments = Assessment.objects.filter(
        course__in=courses, status='published'
    ).select_related('course').prefetch_related('questions__clos', 'questions__plos').order_by('-created_at')
    submissions = {
        s.assessment_id: s
        for s in Submission.objects.filter(student=request.user, assessment__in=assessments)
    }
    assignments_with_status = []
    for a in assessments:
        sub    = submissions.get(a.id)
        window = check_submission_window(a) if not sub else None
        assignments_with_status.append((a, sub, window))
    return render(request, 'student/assignments.html', {
        'assignments_with_status': assignments_with_status,
    })


@student_required
def submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assessment, id=assignment_id, status='published')
    if not Enrollment.objects.filter(student=request.user, course=assignment.course).exists():
        return JsonResponse({'error': 'You are not enrolled in this course.'}, status=403)
    if Submission.objects.filter(student=request.user, assessment=assignment).exists():
        return JsonResponse({'error': 'You have already submitted this assignment.'}, status=400)

    # ── Submission window check ────────────────────────────────────────
    window = check_submission_window(assignment)
    if not window['can_submit']:
        return JsonResponse({'error': window['window_msg']}, status=403)

    if request.method == 'POST':
        content       = request.POST.get('content', '').strip()
        uploaded_file = request.FILES.get('submitted_file')
        if not content and not uploaded_file:
            return JsonResponse({'error': 'Please provide an answer or upload a file.'}, status=400)
        sub = Submission.objects.create(
            student=request.user,
            assessment=assignment,
            content=content,
            submitted_file=uploaded_file,
        )
        apply_late_deduction(sub)
        return JsonResponse({
            'success':    True,
            'is_late':    window['is_late'],
            'window_msg': window['window_msg'],
        })
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def faculty_marks_sheet(request):
    courses = Course.objects.filter(faculty=request.user)
    selected_course = None

    course_id = request.GET.get('course')
    if course_id:
        selected_course = get_object_or_404(Course, id=course_id, faculty=request.user)
    elif courses.exists():
        selected_course = courses.first()

    if not selected_course:
        return render(request, 'faculty/marks_sheet.html', {'courses': courses, 'selected_course': None})

    assessments = list(
        Assessment.objects.filter(course=selected_course, status='published')
        .prefetch_related('questions__clos', 'questions__plos')
        .order_by('assessment_type', 'created_at')
    )

    all_columns = []
    assessment_groups = []
    for a in assessments:
        questions = list(a.questions.all().order_by('order'))
        if not questions:
            continue
        assessment_groups.append({'assessment': a, 'questions': questions, 'col_count': len(questions)})
        for q in questions:
            all_columns.append({
                'assessment': a,
                'question': q,
                'clo_ids': [c.id for c in q.clos.all()],
                'plo_ids': [p.id for p in q.plos.all()],
                'clo_codes': [c.code for c in q.clos.all()],
                'plo_codes': [p.code for p in q.plos.all()],
            })

    students = list(
        User.objects.filter(enrollments__course=selected_course)
        .distinct().order_by('full_name', 'username')
    )

    question_ids = [col['question'].id for col in all_columns]
    grades = QuestionGrade.objects.filter(
        question_id__in=question_ids,
        submission__assessment__course=selected_course
    ).select_related('submission__student')

    grade_map = {}
    for g in grades:
        sid = g.submission.student_id
        grade_map.setdefault(sid, {})[g.question_id] = g.marks_obtained

    clos = list(selected_course.clos.all().order_by('code'))
    plo_ids_used = set()
    for col in all_columns:
        plo_ids_used.update(col['plo_ids'])
    plos = list(PLO.objects.filter(id__in=plo_ids_used).order_by('code'))

    clo_max = {
        clo.id: sum(col['question'].max_marks for col in all_columns if clo.id in col['clo_ids'])
        for clo in clos
    }
    plo_max = {
        plo.id: sum(col['question'].max_marks for col in all_columns if plo.id in col['plo_ids'])
        for plo in plos
    }
    total_max = sum(col['question'].max_marks for col in all_columns)

    rows = []
    for i, student in enumerate(students):
        sg = grade_map.get(student.id, {})
        cells = [
            {'question_id': col['question'].id, 'max_marks': col['question'].max_marks,
             'value': sg.get(col['question'].id)}
            for col in all_columns
        ]
        total = sum(c['value'] for c in cells if c['value'] is not None)
        clo_cells = [
            {'clo_id': clo.id, 'code': clo.code,
             'raw': sum(sg.get(col['question'].id, 0) for col in all_columns if clo.id in col['clo_ids']),
             'max': clo_max[clo.id]}
            for clo in clos
        ]
        plo_cells = [
            {'plo_id': plo.id, 'code': plo.code,
             'raw': sum(sg.get(col['question'].id, 0) for col in all_columns if plo.id in col['plo_ids']),
             'max': plo_max[plo.id]}
            for plo in plos
        ]
        rows.append({
            'sl': i + 1,
            'student': student,
            'cells': cells,
            'total': total,
            'clo_cells': clo_cells,
            'plo_cells': plo_cells,
        })

    clo_max_list = [{'clo': c, 'max': clo_max[c.id]} for c in clos]
    plo_max_list = [{'plo': p, 'max': plo_max[p.id]} for p in plos]
    t2_colspan = 2 + 3 * (len(clos) + len(plos))

    js_columns = json.dumps([
        {'qid': col['question'].id, 'max': col['question'].max_marks,
         'clo_ids': col['clo_ids'], 'plo_ids': col['plo_ids']}
        for col in all_columns
    ])
    js_clos = json.dumps([{'id': c.id, 'code': c.code, 'max': clo_max[c.id]} for c in clos])
    js_plos = json.dumps([{'id': p.id, 'code': p.code, 'max': plo_max[p.id]} for p in plos])

    return render(request, 'faculty/marks_sheet.html', {
        'courses': courses,
        'selected_course': selected_course,
        'assessment_groups': assessment_groups,
        'all_columns': all_columns,
        'rows': rows,
        'clos': clos,
        'plos': plos,
        'clo_max': clo_max,
        'plo_max': plo_max,
        'total_max': total_max,
        'clo_max_list': clo_max_list,
        'plo_max_list': plo_max_list,
        't2_colspan': t2_colspan,
        'js_columns': js_columns,
        'js_clos': js_clos,
        'js_plos': js_plos,
    })


@faculty_required
def update_question_grade(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    data = json.loads(request.body)
    try:
        marks = float(data.get('marks', 0))
    except (TypeError, ValueError):
        marks = 0

    question = get_object_or_404(Question, id=data.get('question_id'),
                                  assessment__course__faculty=request.user)
    student = get_object_or_404(User, id=data.get('student_id'))
    marks = min(max(marks, 0), question.max_marks)

    submission, _ = Submission.objects.get_or_create(
        student=student, assessment=question.assessment,
        defaults={'content': '', 'status': 'graded', 'total_score': 0,
                  'plagiarism_score': 0, 'ai_content_score': 0}
    )
    QuestionGrade.objects.update_or_create(
        submission=submission, question=question,
        defaults={'marks_obtained': marks}
    )
    total = sum(g.marks_obtained for g in QuestionGrade.objects.filter(submission=submission))
    submission.total_score = total
    if submission.status == 'submitted':
        submission.status = 'graded'
    submission.save()
    return JsonResponse({'success': True, 'marks': marks, 'total': total})


@student_required
def get_unread_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})
 
 
@student_required
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})




# QUESTION BANK VIEWS



@faculty_required
def faculty_question_bank(request):
    from .models import PastPaper
    courses = Course.objects.filter(faculty=request.user)
    papers  = PastPaper.objects.filter(
        uploaded_by=request.user
    ).prefetch_related('questions', 'allowed_courses')
    return render(request, 'faculty/question_bank.html', {
        'papers':  papers,
        'courses': courses,
    })


@faculty_required
def create_past_paper(request):
    from .models import PastPaper, PastPaperQuestion
    if request.method == 'POST':
        data = json.loads(request.body)
        paper = PastPaper.objects.create(
            title         = data['title'],
            course_code   = data['course_code'],
            course_name   = data['course_name'],
            semester      = data['semester'],
            exam_type     = data['exam_type'],
            total_marks   = int(data.get('total_marks', 0)),
            duration_mins = int(data.get('duration_mins', 0)),
            description   = data.get('description', ''),
            is_public     = data.get('is_public', False),
            uploaded_by   = request.user,
        )
        course_ids = data.get('allowed_course_ids', [])
        if course_ids:
            paper.allowed_courses.set(
                Course.objects.filter(id__in=course_ids, faculty=request.user)
            )
        total = 0
        for i, q in enumerate(data.get('questions', []), 1):
            PastPaperQuestion.objects.create(
                paper       = paper,
                order       = i,
                text        = q['text'],
                marks       = int(q.get('marks', 0)),
                answer_hint = q.get('answer_hint', ''),
                show_hint   = q.get('show_hint', False),
                topic_tag   = q.get('topic_tag', ''),
                difficulty  = q.get('difficulty', ''),
            )
            total += int(q.get('marks', 0))
        if total > 0:
            paper.total_marks = total
            paper.save(update_fields=['total_marks'])
        return JsonResponse({'success': True, 'id': paper.id})
    return JsonResponse({'error': 'POST required'}, status=400)


@faculty_required
def delete_past_paper(request, paper_id):
    from .models import PastPaper
    paper = get_object_or_404(PastPaper, id=paper_id, uploaded_by=request.user)
    paper.delete()
    return JsonResponse({'success': True})


@faculty_required
def toggle_paper_visibility(request, paper_id):
    from .models import PastPaper
    paper = get_object_or_404(PastPaper, id=paper_id, uploaded_by=request.user)
    paper.is_public = not paper.is_public
    paper.save(update_fields=['is_public'])
    return JsonResponse({'success': True, 'is_public': paper.is_public})


@faculty_required
def toggle_hint_visibility(request, question_id):
    from .models import PastPaperQuestion
    q = get_object_or_404(PastPaperQuestion, id=question_id,
                          paper__uploaded_by=request.user)
    q.show_hint = not q.show_hint
    q.save(update_fields=['show_hint'])
    return JsonResponse({'success': True, 'show_hint': q.show_hint})


@student_required
def student_question_bank(request):
    from .models import PastPaper
    from django.db.models import Q
    enrolled_ids = Enrollment.objects.filter(
        student=request.user
    ).values_list('course_id', flat=True)

    papers = PastPaper.objects.filter(
        Q(is_public=True) | Q(allowed_courses__id__in=enrolled_ids)
    ).distinct().prefetch_related('questions')

    # Filters
    search      = request.GET.get('q', '').strip()
    exam_type   = request.GET.get('type', '')
    semester    = request.GET.get('semester', '')
    course_code = request.GET.get('course', '')
    difficulty  = request.GET.get('difficulty', '')

    if search:
        papers = papers.filter(
            Q(title__icontains=search) |
            Q(course_code__icontains=search) |
            Q(course_name__icontains=search) |
            Q(questions__text__icontains=search) |
            Q(questions__topic_tag__icontains=search)
        ).distinct()
    if exam_type:
        papers = papers.filter(exam_type=exam_type)
    if semester:
        papers = papers.filter(semester__icontains=semester)
    if course_code:
        papers = papers.filter(course_code__icontains=course_code)
    if difficulty:
        papers = papers.filter(questions__difficulty=difficulty).distinct()

    all_accessible = PastPaper.objects.filter(
        Q(is_public=True) | Q(allowed_courses__id__in=enrolled_ids)
    ).distinct()

    return render(request, 'student/question_bank.html', {
        'papers':       papers,
        'total_count':  papers.count(),
        'course_codes': sorted(set(all_accessible.values_list('course_code', flat=True))),
        'semesters':    sorted(set(all_accessible.values_list('semester', flat=True)), reverse=True),
        'search':       search,
        'exam_type':    exam_type,
        'semester':     semester,
        'course_code':  course_code,
        'difficulty':   difficulty,
    })


@student_required
def student_view_paper(request, paper_id):
    from .models import PastPaper
    from django.db.models import Q
    enrolled_ids = Enrollment.objects.filter(
        student=request.user
    ).values_list('course_id', flat=True)

    paper = get_object_or_404(PastPaper, id=paper_id)

    # Permission check
    if not paper.is_public:
        if not paper.allowed_courses.filter(id__in=enrolled_ids).exists():
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("You don't have access to this paper.")

    return render(request, 'student/view_paper.html', {
        'paper':     paper,
        'questions': paper.questions.all(),
    })