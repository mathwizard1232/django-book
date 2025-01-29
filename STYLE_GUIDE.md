# LibraCents Style Guide

This document serves as an internal guide for maintaining consistency in the LibraCents codebase. While anyone is welcome to read and follow these guidelines, they primarily exist as reminders for the core development team and AI assistance.

## Core Principles

### 1. Avoid Session State Dependencies

We avoid using session state whenever possible, treating it like a global variable that requires strong justification. All necessary data should be passed through forms explicitly.

#### Bad Example
```python
# Don't store author data in session
session['selected_author_olid'] = author.olid
session['selected_author_name'] = author.primary_name
```

#### Good Example
```python
# Pass data through form fields
class ConfirmAuthorForm(forms.Form):
    author_olid = forms.CharField(widget=forms.HiddenInput())
    author_name = forms.CharField(label='Author Name')
```

Reference: See test_book_search_integration.py [lines 102-168] for examples of tests we're actively moving away from session dependencies.

### 2. Test-First Development

New features should be developed with testing in mind from the start. This means:

1. Write tests before implementing features when possible
2. Make forms and UI elements easily targetable by automated tests
3. Use clear, consistent IDs and labels for interactive elements

#### Good Example
```html
<!-- Use clear IDs for test targeting -->
<input type="submit" id="confirm-without-shelving" value="Confirm Without Shelving">
```

Reference: See test_author_search.py [lines 1-323] for comprehensive examples of well-structured tests.

### 3. File Size and Organization

Monitor file sizes and complexity. Consider refactoring when:
- Files approach ~1000 lines
- A single class or function becomes difficult to understand
- Multiple concerns are mixed in one file

#### Signs You Need to Split a File:
- Multiple unrelated class definitions
- Long, complex test classes with many scenarios
- Views handling multiple distinct features

Reference: book_views.py is a candidate for splitting based on these guidelines.

### 4. Documentation

- Include docstrings for classes and non-obvious methods
- Comment complex business logic
- Keep README updated with new features and changes
- Document test patterns and fixtures

### 5. UI/UX Consistency

- Use consistent styling for forms
- Maintain consistent button labeling
- Keep user flows simple and predictable

Reference: See base.html [lines 10-68] for consistent styling patterns.

## Maintenance

This style guide should evolve with the project. When patterns emerge that help maintain code quality and developer sanity, they should be added here.

Remember: These guidelines exist to make development easier and more maintainable, not to create unnecessary restrictions. Use judgment when applying them. 

### 6. Avoid unnecessary redirects

- Instead of using an HTTP redirect, use internal function calls when possible