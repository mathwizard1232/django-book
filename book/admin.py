from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.apps import apps
from .models import Work, Edition, Copy, Author, OpenLibraryCache

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('primary_name', 'olid', 'search_name')
    search_fields = ('primary_name', 'search_name', 'olid')
    list_filter = ('work__type',)  # Filter by types of works they've written
    actions = ['delete_selected']  # Explicitly enable delete action

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

class BookAdminSite(admin.AdminSite):
    index_template = 'admin/book/index.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('wipe-database/', self.admin_view(self.wipe_database_view), name='wipe-database'),
        ]
        return custom_urls + urls

    def index(self, request, extra_context=None):
        """Override index to add the wipe database button"""
        extra_context = extra_context or {}
        extra_context['show_wipe_button'] = True
        print("Debug: Setting show_wipe_button to True")  # Debug print
        return super().index(request, extra_context)

    def wipe_database_view(self, request):
        if request.method == 'POST' and request.POST.get('confirm'):
            # Reuse the logic from the migration
            Book = apps.get_model('book', 'Book')
            Copy = apps.get_model('book', 'Copy')
            Edition = apps.get_model('book', 'Edition')
            Work = apps.get_model('book', 'Work')
            Author = apps.get_model('book', 'Author')
            OpenLibraryCache = apps.get_model('book', 'OpenLibraryCache')
            Location = apps.get_model('book', 'Location')
            Room = apps.get_model('book', 'Room')
            Bookcase = apps.get_model('book', 'Bookcase')
            Shelf = apps.get_model('book', 'Shelf')
            Box = apps.get_model('book', 'Box')
            BookGroup = apps.get_model('book', 'BookGroup')
            
            # Clear all data in reverse dependency order
            Book.objects.all().delete()
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
            
            messages.success(request, "All data has been wiped from the database.")
            return HttpResponseRedirect(reverse('admin:index'))
            
        return render(
            request,
            'admin/wipe_confirmation.html',
            context={'title': 'Wipe Database'}
        )

# Create custom admin site instance
admin_site = BookAdminSite(name='admin')

# Register all models with the custom admin site
admin_site.register(Author, AuthorAdmin)
admin_site.register(Work, WorkAdmin)
admin_site.register(Edition, EditionAdmin)
admin_site.register(Copy, CopyAdmin)
admin_site.register(OpenLibraryCache, OpenLibraryCacheAdmin) 