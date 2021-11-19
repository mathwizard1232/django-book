from django import forms

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
    """ Confirm a given book is the desired selection """
    title = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    author_name = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    author_olid = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    work_olid = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    