from pathlib import Path

from django.db import migrations, models


def populate_original_filename(apps, schema_editor):
    Resume = apps.get_model("core", "Resume")
    for resume in Resume.objects.all().iterator():
        if resume.original_filename:
            continue
        file_name = Path(str(resume.original_file)).name if resume.original_file else ""
        if file_name:
            resume.original_filename = file_name
            resume.save(update_fields=["original_filename"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_job_created_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="resume",
            name="original_filename",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.RunPython(populate_original_filename, migrations.RunPython.noop),
    ]
