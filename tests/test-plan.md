# Test Plan for LibraCents

## Overview
This test plan outlines the automated testing strategy for LibraCents, focusing on end-to-end testing using Selenium to ensure core functionality remains intact during development.

## Test Environment Setup
- Python with Selenium WebDriver
- Chrome/Firefox WebDriver
- Django test server
- Test database with predefined fixtures
- Mock OpenLibrary API responses for consistent testing

## Core Test Scenarios

### 1. Book Entry Flow
#### 1.1 Basic Book Entry
- Test author-first search workflow
- Verify local author results appear before OpenLibrary results
- Confirm new author entry process
- Verify title search and confirmation
- Test basic shelving process

#### 1.2 Multiple Copy Handling
- Test entering duplicate books
- Verify copy counting
- Test different location assignments for copies
- Verify copy distinction in the system

#### 1.3 ISBN Entry Flow
- Test direct ISBN entry
- Verify OpenLibrary ISBN lookup
- Test handling of invalid ISBNs
- Verify local database check before external lookup
- Test SBN conversion and lookup

#### 1.4 Editor Entry Flow
- Test adding book with editor instead of author
- Verify editor role assignment
- Test mixed author/editor entries
- Verify editor display in book listings

#### 1.5 Multiple Author Works
- Test adding work with multiple authors
- Verify author order preservation
- Test author role assignments
- Verify author display order in listings
- Test editing author list post-creation

#### 1.6 Collection Management
- Test creating collection from two works
- Verify parent-child work relationships
- Test collection with mixed author sets
- Verify collection display in listings
- Test adding works to existing collection
- Test removing works from collection

#### 1.7 Multi-Volume Works
- Test complete volume set entry
- Test single volume entry
- Test partial volume set entry
- Verify volume numbering
- Test volume reordering
- Verify volume display in listings

### 2. Location Management
#### 2.1 Location Hierarchy
- Test location creation
- Test room addition to locations
- Test bookcase management
- Test shelf assignment
- Verify hierarchical display and navigation

#### 2.2 Book Shelving
- Test assigning books to locations
- Test moving books between locations
- Test bulk shelving operations
- Verify location tracking accuracy

### 3. Search and Retrieval
#### 3.1 Search Functionality
- Test author search
- Test title search
- Test combined search criteria
- Verify result ordering and relevance

#### 3.2 Location-based Retrieval
- Test finding books by location
- Test finding books by shelf
- Test finding all copies of a work
- Verify location hierarchy navigation

## Implementation Priority

### Phase 1: Core Entry Flow
1. Basic author search and selection
2. Title search and confirmation
3. Simple location assignment
4. Basic copy tracking

### Phase 2: Location Management
1. Location hierarchy navigation
2. Book shelving operations
3. Bulk operations
4. Location tracking accuracy

### Phase 3: Search and Retrieval
1. Basic search functionality
2. Location-based retrieval
3. Advanced search features
4. Result filtering and sorting

## Test Implementation Guidelines

### Test Structure
- Use page object pattern for maintainable tests
- Implement base test class with common setup/teardown
- Use fixtures for consistent test data
- Mock external API calls

### Test Data Management
- Create fixtures for:
  - Sample authors
  - Sample works
  - Location hierarchy
  - User data
- Mock OpenLibrary API responses

### Continuous Integration
- Run tests on pull requests
- Run nightly against main branch
- Generate test coverage reports
- Track test execution times

### Test Data Requirements

#### Collection Test Data
- Sample collections with multiple works
- Works with multiple authors
- Works with editor credits
- Multi-volume work sets
- Mixed author/editor credits

#### Special Case Fixtures
- Works with ISBNs and SBNs
- Works with multiple editions
- Collections with nested collections
- Works with complex author relationships

### Error Handling Tests
- Test missing author/editor data
- Test invalid volume numbers

### UI/UX Tests
- Verify author/editor role selection UI
- Test collection creation workflow
- Verify volume number input interface
- Test multiple author entry interface
- Verify error message display
- Test navigation between entry modes

## Next Steps
1. Set up basic test infrastructure
2. Implement Phase 1 tests
3. Add CI integration
4. Expand test coverage based on priority 