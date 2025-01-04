from django.contrib import admin
from .models import Work, Edition, Copy, Author

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('primary_name', 'olid', 'search_name')
    search_fields = ('primary_name', 'search_name', 'olid')
    list_filter = ('work__type',)  # Filter by types of works they've written

class EditionInline(admin.TabularInline):
    model = Edition
    extra = 0

class CopyInline(admin.TabularInline):
    model = Copy
    extra = 0

@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ('title', 'get_authors', 'type', 'is_multivolume', 'volume_number')
    list_filter = ('type', 'is_multivolume')
    search_fields = ('title', 'search_name', 'authors__primary_name')
    filter_horizontal = ('authors', 'component_works')
    inlines = [EditionInline]
    
    def get_authors(self, obj):
        return ", ".join([str(author) for author in obj.authors.all()])
    get_authors.short_description = 'Authors'

@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = ('work', 'publisher', 'format')
    list_filter = ('format',)
    search_fields = ('work__title', 'publisher')
    inlines = [CopyInline]

@admin.register(Copy)
class CopyAdmin(admin.ModelAdmin):
    list_display = ('edition', 'condition', 'location', 'room', 'bookcase', 'shelf')
    list_filter = ('condition', 'location', 'room', 'bookcase')
    search_fields = ('edition__work__title', 'edition__publisher') 