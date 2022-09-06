# django-book
First draft proof-of-concept of fast book identification with data provided by OpenLibrary via their API and python client

## Credits

Background photo of old books taken by ben.gallagher of St John's College Old Library from https://www.flickr.com/photos/26848985@N02/4101516350 via https://search.creativecommons.org/photos/da0fe7d4-981e-4077-b691-d3e7c3435bd4

Background image of scroll by Diego da Silva from https://www.flickr.com/photos/35745518@N04/4306058967 via https://search.creativecommons.org/photos/9607560f-8683-4ae4-aca8-ba5d80eb3d9e

Licenses under https://creativecommons.org/licenses/by/2.0/ with attribution.

## Requirements
- Python

- Install [OpenLibrary python client](https://github.com/internetarchive/openlibrary-client)

- Install Django; `pip install django`

- Apply migrations: `python3 manage.py migrate`

## Running

`python3 manage.py runserver`

Index page just directs to `/author`, which is author selection page and starts process.

## Process

This software is used to do a fast lookup of a book, for entry or checking presence.

First, an author is selected. Then a title.

In both author and title selection, any local results are used first. When starting out or for authors or titles
not previously seen, the OpenLibrary API is called for lookup and confirmation screens are used for the new entries.

## Known issues

* No index page
* Lookup of author should give more information on confirmation
* Lookup of book should give more information on confirmation
* Change author confirmation page when there's no alternate to not just have empty alternate box

## Wishlist

* Add a mode for switching between "slow" ("this book has now been entered" with options), or "repeat author" (input set of one author) or "repeat entry" (input series of books) ; this saves a click at the end of entry for on-going sets (currently hardcoded to fast after duplicate titles)
* Remote backup and restore capabilities
* Custom entry for books not found
* Search by title for collections with many authors (e.g. sci fi short story compilations)
* Search by title for author to fallback to search by title when book not found by author?
* Listing page / search page
* Add entry by ISBN
  * And by SBN
* Add better disambiguation when e.g. wrong edition of book? (though in theory current "Book" just content id)
* Better handling of no result in confirm book
* Split out base and autocomplete-base templates
