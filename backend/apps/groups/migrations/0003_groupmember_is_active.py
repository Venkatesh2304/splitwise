from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('groups', '0002_groupmember_last_seen_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupmember',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
