from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_documentation_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='ai_config',
            field=models.JSONField(default=dict),
        ),
    ]
