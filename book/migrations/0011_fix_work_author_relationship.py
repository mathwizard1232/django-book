from django.db import migrations, models

def preserve_work_author_relationships(apps, schema_editor):
    """
    Temporarily store and restore work-author relationships during the primary key change
    """
    Work = apps.get_model('book', 'Work')
    Author = apps.get_model('book', 'Author')
    
    # Store all existing relationships
    author_relationships = []
    editor_relationships = []
    
    for work in Work.objects.all():
        # Store author relationships
        for author in work.authors.all():
            author_relationships.append((work.id, author.olid))
        # Store editor relationships
        for editor in work.editors.all():
            editor_relationships.append((work.id, editor.olid))
    
    # Clear both M2M tables to allow for schema change
    for work in Work.objects.all():
        work.authors.clear()
        work.editors.clear()
    
    # Restore relationships using the new ID-based system
    for work_id, author_olid in author_relationships:
        work = Work.objects.get(id=work_id)
        author = Author.objects.get(olid=author_olid)
        work.authors.add(author)
        
    for work_id, editor_olid in editor_relationships:
        work = Work.objects.get(id=work_id)
        editor = Author.objects.get(olid=editor_olid)
        work.editors.add(editor)

def reverse_relationships(apps, schema_editor):
    """
    Reverse migration is similar but in reverse direction
    """
    Work = apps.get_model('book', 'Work')
    Author = apps.get_model('book', 'Author')
    
    # Store relationships
    author_relationships = []
    editor_relationships = []
    
    for work in Work.objects.all():
        for author in work.authors.all():
            author_relationships.append((work.id, author.olid))
        for editor in work.editors.all():
            editor_relationships.append((work.id, editor.olid))
    
    # Clear the M2M tables
    for work in Work.objects.all():
        work.authors.clear()
        work.editors.clear()
    
    # Restore using the old system
    for work_id, author_olid in author_relationships:
        work = Work.objects.get(id=work_id)
        author = Author.objects.get(olid=author_olid)
        work.authors.add(author)
        
    for work_id, editor_olid in editor_relationships:
        work = Work.objects.get(id=work_id)
        editor = Author.objects.get(olid=editor_olid)
        work.editors.add(editor)

class Migration(migrations.Migration):
    dependencies = [
        ('book', '0010_author_id_alter_author_olid'),
    ]

    operations = [
        # Store existing relationships
        migrations.RunPython(
            preserve_work_author_relationships,
            reverse_code=reverse_relationships
        ),
        # Remove and recreate the authors M2M relationship
        migrations.RemoveField(
            model_name='work',
            name='authors',
        ),
        migrations.AddField(
            model_name='work',
            name='authors',
            field=models.ManyToManyField('Author'),
        ),
        # Remove and recreate the editors M2M relationship
        migrations.RemoveField(
            model_name='work',
            name='editors',
        ),
        migrations.AddField(
            model_name='work',
            name='editors',
            field=models.ManyToManyField('Author', related_name='edited_works'),
        ),
    ] 