from django import forms

class AuthorForm(forms.Form):
    """ Input to get user version of author name """
    author_name = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'autofocus': 'autofocus'}))

class ConfirmAuthorForm(forms.Form):
    """ Readonly version showing lookup results """
    author_name = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    olid = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))

class TitleForm(forms.Form):
    """ Input to get user version of a title """
    title = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'autofocus': 'autofocus'}))

class TitleGivenAuthorForm(forms.Form):
    """ Get a given title from a given author's works """
    author_name = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    olid = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'readonly': True}))
    # Required=False needed or shows a validation error when rendered
    title = forms.CharField(max_length=100,
        widget=forms.TextInput(attrs={'autofocus': 'autofocus'}), required=False)
