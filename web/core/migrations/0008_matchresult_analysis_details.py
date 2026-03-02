from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_jobrefreshstate"),
    ]

    operations = [
        migrations.AddField(
            model_name="matchresult",
            name="analysis_details",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
