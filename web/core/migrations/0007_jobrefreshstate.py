from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_resume_original_filename"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobRefreshState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("last_attempted_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("last_source", models.CharField(blank=True, default="", max_length=32)),
                ("last_error", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
