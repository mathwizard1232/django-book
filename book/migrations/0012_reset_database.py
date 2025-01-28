from django.db import migrations

def clear_all_data(apps, schema_editor):
    """Clear all data from the database"""
    Work = apps.get_model('book', 'Work')
    Author = apps.get_model('book', 'Author')
    Edition = apps.get_model('book', 'Edition')
    Copy = apps.get_model('book', 'Copy')
    OpenLibraryCache = apps.get_model('book', 'OpenLibraryCache')
    Location = apps.get_model('book', 'Location')
    Room = apps.get_model('book', 'Room')
    Bookcase = apps.get_model('book', 'Bookcase')
    Shelf = apps.get_model('book', 'Shelf')
    Box = apps.get_model('book', 'Box')
    BookGroup = apps.get_model('book', 'BookGroup')
    Book = apps.get_model('book', 'Book')  # Add the old Book model
    
    # Clear all data in reverse dependency order
    Book.objects.all().delete()  # Clear old Book model first
    Copy.objects.all().delete()
    Edition.objects.all().delete()
    Work.objects.all().delete()
    Author.objects.all().delete()
    OpenLibraryCache.objects.all().delete()
    Shelf.objects.all().delete()
    Box.objects.all().delete()
    Bookcase.objects.all().delete()
    Room.objects.all().delete()
    Location.objects.all().delete()
    BookGroup.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('book', '0011_fix_work_author_relationship'),
    ]

    operations = [
        migrations.RunPython(
            clear_all_data,
            reverse_code=migrations.RunPython.noop
        ),
    ] 