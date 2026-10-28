from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_userprofile_swiggy_pkce_verifier'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='swiggy_token_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='swiggy_oauth_state',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='swiggy_oauth_redirect_uri',
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
    ]
