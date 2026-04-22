from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0010_grace_period'),
    ]

    operations = [
        migrations.CreateModel(
            name='PastPaper',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title',         models.CharField(max_length=200)),
                ('course_code',   models.CharField(max_length=20)),
                ('course_name',   models.CharField(max_length=200)),
                ('semester',      models.CharField(max_length=50)),
                ('exam_type',     models.CharField(max_length=20, choices=[
                    ('mid',        'Mid Exam'),
                    ('final',      'Final Exam'),
                    ('ct',         'Class Test'),
                    ('quiz',       'Quiz'),
                    ('assignment', 'Assignment'),
                ])),
                ('total_marks',   models.IntegerField(default=0)),
                ('duration_mins', models.IntegerField(default=0)),
                ('description',   models.TextField(blank=True)),
                ('is_public',     models.BooleanField(default=False)),
                ('uploaded_by',   models.ForeignKey(settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='past_papers')),
                ('uploaded_at',   models.DateTimeField(auto_now_add=True)),
                ('allowed_courses', models.ManyToManyField('Course', blank=True,
                    related_name='past_papers')),
            ],
            options={'ordering': ['-uploaded_at']},
        ),
        migrations.CreateModel(
            name='PastPaperQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('paper',       models.ForeignKey('PastPaper',
                    on_delete=django.db.models.deletion.CASCADE, related_name='questions')),
                ('order',       models.IntegerField(default=1)),
                ('text',        models.TextField()),
                ('marks',       models.IntegerField(default=0)),
                ('answer_hint', models.TextField(blank=True)),
                ('show_hint',   models.BooleanField(default=False)),
                ('topic_tag',   models.CharField(max_length=100, blank=True)),
                ('difficulty',  models.CharField(max_length=10, blank=True, choices=[
                    ('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard'),
                ])),
            ],
            options={'ordering': ['order']},
        ),
    ]