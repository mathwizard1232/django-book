from django.contrib import admin
from .models import Work, Edition, Copy, Author, OpenLibraryCache

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

@admin.register(OpenLibraryCache)
class OpenLibraryCacheAdmin(admin.ModelAdmin):
    list_display = ('request_url', 'last_updated', 'cache_duration', 'response_preview')
    search_fields = ('request_url',)
    readonly_fields = ('last_updated',)
    list_filter = ('last_updated',)
    ordering = ('-last_updated',)
    
    def response_preview(self, obj):
        """Preview first 100 characters of response"""
        return f"{str(obj.response_data)[:100]}..."
    response_preview.short_description = 'Response Preview'
    
    actions = ['clear_cache']
    
    def clear_cache(self, request, queryset):
        """Admin action to clear selected cache entries"""
        deleted_count = queryset.delete()[0]
        if deleted_count == 1:
            message = '1 cache entry was'
        else:
            message = f'{deleted_count} cache entries were'
        self.message_user(request, f"{message} successfully cleared.")
    clear_cache.short_description = "Clear selected cache entries" 