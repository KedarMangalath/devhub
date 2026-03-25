from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_project_ai_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='metadata',
            field=models.JSONField(default=dict),
        ),
    ]
