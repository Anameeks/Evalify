from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0011_past_paper'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assessment',
            name='assessment_type',
            field=models.CharField(
                choices=[
                    ('assignment', 'Assignment'),
                    ('quiz', 'Quiz'),
                    ('mid', 'Mid Exam'),
                    ('ct', 'Class Test'),
                    ('final', 'Final Exam'),
                    ('lab', 'Lab Task'),
                ],
                max_length=20,
            ),
        ),
    ]
