# django-book
Test project with autocompletion of author search powered by OpenLibrary

## Requirements
Install [OpenLibrary python client](https://github.com/internetarchive/openlibrary-client)

Install Django; `pip install django`

## Running

`./manage.py runserver`

Currently no index page. Start at `/author`.

## Known issues

* Book isn't actually saved
* Confirm book returns None / breaks flow
* No auto-complete on author
* No index page