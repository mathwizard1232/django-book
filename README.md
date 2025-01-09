# LibraCents (or maybe Super Book or maybe Django-Book)
A value-conscious personal library management system that prioritizes quick, efficient book entry and organization.

## Credits

Background photo of old books taken by ben.gallagher of St John's College Old Library from https://www.flickr.com/photos/26848985@N02/4101516350 via https://search.creativecommons.org/photos/da0fe7d4-981e-4077-b691-d3e7c3435bd4

Background image of scroll by Diego da Silva from https://www.flickr.com/photos/35745518@N04/4306058967 via https://search.creativecommons.org/photos/9607560f-8683-4ae4-aca8-ba5d80eb3d9e

Licenses under https://creativecommons.org/licenses/by/2.0/ with attribution.

Written with assistance from AI: Claude 3.5 Sonnet via Cursor IDE.

## Overview
LibraCents helps you manage your personal library with a focus on both organizational efficiency and collection value. It stands apart from other library management systems by:

- Optimizing the book entry process beyond just ISBN scanning
- Supporting flexible physical organization (shelves, boxes, rooms)
- Helping track the value and investment in your collection (Coming Soon(tm))
- Maintaining clear distinctions between Works, Editions, and physical Copies (Coming Soon(tm) (internally represented currently but not yet displayed or used beyond representing multiple copies of the same work))

## Key Features
- Fast book identification through author-first search
- Integration with OpenLibrary for comprehensive book data
- Support for both simple and detailed location tracking
- Bulk operations for managing boxed collections (Coming Soon(tm))
- Local-first data with optional external lookups

## Requirements
- Python
- OpenLibrary Python client
- Django

### Installation
```bash
pip install git+https://github.com/internetarchive/openlibrary-client.git
pip install git+https://github.com/mathwizard1232/openlibrary-client-2.git
pip install django
python3 manage.py migrate
```

## Running
```bash
python3 manage.py runserver
```

## Process
This software is used to do a fast lookup of a book, for entry or checking presence.

First, an author is selected. Then a title.

In both author and title selection, any local results are used first. When starting out or for authors or titles
not previously seen, the OpenLibrary API is called for lookup and confirmation screens are used for the new entries.

## Known Issues
* Need to decide how to handle complete sets for list view (probably hide the individual volumes and show the overall multivolume Work vs currently it appears as unshelved; leaving for now until I get back to reshelving)
* Lookup of author should give more information on confirmation
* Lookup of book should give more information on confirmation
* Visuals/UX inconsistent (UI text with background color set or not / CSS breaks)

## Wishlist
* Build out list / search of library: browse / find by author, etc
* Better support for multiple author ids for same author in OpenLibrary
  * Maybe instead of primary / alternative, default to primary with a list of alternatives, then option to select a different author instead? (Basically, do some logic to detect if any multiple results are likely the same author or different and branch accordingly, but go to a default author and enter title rather than always require the extra step on new author)
* Similarly for Works, might want to just default to primary (not even bother with trying to identify other Work ids for the moment; deal with this when dealing with Edition details (because a desired Edition might be under a different Work id, but at basic Work/Copy level we don't care)) with option to select something else.
* Add a mode for switching between "slow" ("this book has now been entered" with options), or "repeat author" (input set of one author) or "repeat entry" (input series of books) ; this saves a click at the end of entry for on-going sets (currently hardcoded to fast after duplicate titles)
* Remote backup and restore capabilities
* Custom entry for books not found
* Search by title for collections with many authors (e.g. sci fi short story compilations)
* Search page
* Add entry by ISBN
  * And by SBN
* Add better disambiguation when e.g. wrong edition of book? (though in theory current "Book" just content id)
* Better handling of no result in confirm book
* Split out base and autocomplete-base templates
* Book valuation external sources & logic
