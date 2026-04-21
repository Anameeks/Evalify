from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evalify_app', '0009_merge_0007_notification_0008_delete_studentprofile'),
    ]

    operations = [
        # Assessment — grace period settings
        migrations.AddField(
            model_name='assessment',
            name='grace_period_hours',
            field=models.IntegerField(
                default=0,
                help_text='Extra hours allowed after due date (0 = no grace period)',
            ),
        ),
        migrations.AddField(
            model_name='assessment',
            name='late_deduction_type',
            field=models.CharField(
                max_length=10,
                choices=[('percent', 'Percent'), ('flat', 'Flat Marks')],
                default='percent',
            ),
        ),
        migrations.AddField(
            model_name='assessment',
            name='late_deduction_value',
            field=models.FloatField(
                default=0,
                help_text='Deduction per late day (percent or flat marks)',
            ),
        ),
        migrations.AddField(
            model_name='assessment',
            name='max_late_days',
            field=models.IntegerField(
                default=0,
                help_text='Max days late allowed after grace period',
            ),
        ),
        # Submission — late tracking fields
        migrations.AddField(
            model_name='submission',
            name='is_late',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='submission',
            name='hours_late',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='submission',
            name='late_deduction',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='submission',
            name='final_score',
            field=models.FloatField(
                default=0,
                help_text='total_score minus late_deduction',
            ),
        ),
    ]