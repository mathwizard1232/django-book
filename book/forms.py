from django import forms
from book.models.location import Location, Room, Bookcase
class AuthorForm(forms.Form):
    """ Input to get user version of author name """
    author_name = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={
            'autofocus': 'autofocus',
            'class': 'basicAutoComplete',
            'data-url': "/author-autocomplete",
            'autocomplete': 'off'
        }))

class ConfirmAuthorForm(forms.Form):
    """ Readonly version showing lookup results """
    # Display version of author name from OpenLibrary
    author_name = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    # OpenLibrary identifier
    author_olid = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    # Name entered by user; alternate lookup
    search_name = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))

class ConfirmAuthorFormWithBio(ConfirmAuthorForm):
    """Additional field for bio if available"""
    bio = forms.CharField(widget=forms.Textarea(attrs={'readonly': True}), required=False)

class TitleForm(forms.Form):
    """ Input to get user version of a title """
    title = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'autofocus': 'autofocus'}))

class TitleGivenAuthorForm(forms.Form):
    """ Get a given title from a given author's works """
    author_name = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    author_olid = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    # Required=False needed or shows a validation error when rendered
    title = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'autofocus': 'autofocus',
            'class': 'basicAutoComplete',
            'data-url': '/title-autocomplete',
            'autocomplete': 'off'}), required=False)

class ConfirmBook(forms.Form):
    """Confirm a given book is the desired selection"""
    # Main visible fields
    title = forms.CharField(max_length=100)
    work_olid = forms.CharField(max_length=100)
    author_olid = forms.CharField(required=False)
    author_name = forms.CharField(required=False)
    publisher = forms.CharField(required=False)
    publish_year = forms.CharField(required=False)
    
    # Role selection for the author
    ROLE_CHOICES = [
        ('AUTHOR', 'Author'),
        ('EDITOR', 'Editor')
    ]
    author_role = forms.ChoiceField(
        choices=ROLE_CHOICES, 
        initial='AUTHOR',
        required=False
    )
    
    # Multi-volume fields - hidden since handled by template
    is_multivolume = forms.BooleanField(widget=forms.HiddenInput(), required=False)
    volume_count = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    volume_number = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    entry_type = forms.CharField(widget=forms.HiddenInput(), required=False)
    
class LocationForm(forms.Form):
    name = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'autofocus': 'autofocus'}))
    type = forms.ChoiceField(choices=Location.TYPE_CHOICES)
    address = forms.CharField(required=False, 
        widget=forms.Textarea(attrs={'rows': 3}))
    notes = forms.CharField(required=False,
        widget=forms.Textarea(attrs={'rows': 3}))
    
class LocationEntityForm(forms.Form):
    ENTITY_TYPES = [
        ('LOCATION', 'Building/Storage Space'),
        ('ROOM', 'Room'),
        ('BOOKCASE', 'Bookcase'),
        ('SHELF', 'Shelf'),
        ('BOX', 'Box'),
        ('GROUP', 'Book Group'),
    ]
    
    entity_type = forms.ChoiceField(
        choices=ENTITY_TYPES,
        label="What type of location are you adding?"
    )
    
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'autofocus': 'autofocus'})
    )
    
    # Location-specific fields
    type = forms.ChoiceField(
        choices=Location.TYPE_CHOICES,
        required=False
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})
    )
    
    # Room-specific fields
    room_type = forms.ChoiceField(
        choices=Room.TYPE_CHOICES,
        required=False
    )
    floor = forms.IntegerField(
        required=False,
        initial=1
    )
    parent_location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="In which building?"
    )
    
    # Bookcase-specific fields
    shelf_count = forms.IntegerField(
        required=False,
        min_value=1
    )
    parent_room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
        required=False,
        label="In which room?"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})
    )
    
class ISBNForm(forms.Form):
    """Input to get book ISBN"""
    isbn = forms.CharField(
        max_length=13,
        widget=forms.TextInput(attrs={
            'autofocus': 'autofocus',
            'placeholder': 'Enter ISBN-10 or ISBN-13'
        })
    )
    