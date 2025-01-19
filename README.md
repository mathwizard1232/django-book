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
* Lookup of author should give more information on confirmation
* Lookup of book should give more information on confirmation
* Visuals/UX inconsistent (UI text with background color set or not / CSS breaks)
* Need to be able to edit/delete Locations through UI
* Need to better support modifying / swapping when OL result is wrong/bad (e.g. "Flame of Iridar" brings back wrong double book instead of individual Work; user should be able to modify title and remove OL reference; OL references should be optional)
* Collection (multiple Works in a Work) entry is not yet working right (not adding authors on parent Work yet; doesn't allow editing component titles; doesn't shelve correctly; etc; need to work on further testing on this flow)

## Wishlist
* Skip author confirmation on exact match
* Skip Work confirmation on exact (or close enough; e.g. case-insensitive etc) match (? Then just shelving confirmation screen to close out in that case? Enter author -> title -> confirm shelf?)
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
* Build out some end-to-end tests to help avoid regressions from refactors etc

## Testing
LibraCents uses end-to-end testing with Selenium WebDriver to ensure core functionality remains intact during development.

### Test Requirements
```bash
pip install -r requirements-test.txt
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest book/tests/test_author_search.py

# Run tests with more detailed output
pytest -v

# Run tests and show print statements
pytest -s
```

### Test Structure
- `book/tests/conftest.py` - Test configuration and fixtures
- `book/tests/pages/` - Page Object Models for test maintainability
  - `base_page.py` - Common page functionality
  - `author_page.py` - Author search and selection
- `book/tests/test_*.py` - Test implementations

### Writing Tests
Tests use the Page Object pattern to maintain separation between test logic and page implementation details. New tests should:
1. Create appropriate page objects in `book/tests/pages/`
2. Use fixtures from `conftest.py` for common setup
3. Mock external API calls (especially OpenLibrary)
4. Follow existing patterns for consistent test structure

See `book/tests/test-plan.md` for complete test coverage goals and implementation priorities.