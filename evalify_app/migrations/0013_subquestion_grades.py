import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0012_add_lab_task_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='image',
            field=models.FileField(blank=True, null=True, upload_to='questions/'),
        ),
        migrations.CreateModel(
            name='SubQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(default=1)),
                ('text', models.TextField()),
                ('image', models.FileField(blank=True, null=True, upload_to='sub_questions/')),
                ('max_marks', models.IntegerField(default=5)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sub_questions', to='evalify_app.question')),
                ('clos', models.ManyToManyField(blank=True, to='evalify_app.clo')),
                ('plos', models.ManyToManyField(blank=True, to='evalify_app.plo')),
            ],
        ),
        migrations.CreateModel(
            name='SubQuestionGrade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('marks_obtained', models.FloatField(default=0)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sub_question_grades', to='evalify_app.submission')),
                ('sub_question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='evalify_app.subquestion')),
            ],
            options={
                'unique_together': {('submission', 'sub_question')},
            },
        ),
    ]
