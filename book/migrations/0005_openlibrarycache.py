# Generated by Django 5.1.4 on 2025-01-03 21:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('book', '0004_edition_bookgroup_location_room_box_bookcase_shelf_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='OpenLibraryCache',
            fields=[
                ('request_url', models.CharField(max_length=2000, primary_key=True, serialize=False)),
                ('response_data', models.JSONField()),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('cache_duration', models.IntegerField(default=24)),
            ],
            options={
                'indexes': [models.Index(fields=['last_updated'], name='book_openli_last_up_6cf4f9_idx')],
            },
        ),
    ]