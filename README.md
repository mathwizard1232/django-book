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
* No index page
* Lookup of author should give more information on confirmation
* Lookup of book should give more information on confirmation

## Wishlist

* Add a mode for switching between "slow" ("this book has now been entered" with options), or "repeat author" (input set of one author) or "repeat entry" (input series of books) ; this saves a click at the end of entry for on-going sets
