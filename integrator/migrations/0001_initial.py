from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Product',
            fields=[
                ('sku', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('payload_hash', models.CharField(blank=True, max_length=64)),
                ('remote_exists', models.BooleanField(default=False)),
                ('last_synced_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
