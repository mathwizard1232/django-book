Current status: Up next: Do 1.2, do a "quick entry", where a default Copy is made once a Work is identified, as first modification of existing flow. Then do a "detailed entry" support for distinguishing multiple copies (determine Edition / try to distinguish Copy). How to do this with
a minimal Copy from the first entry? The second time a book is encountered, it'll be filled out
and then marked that it's been seen a second time, and then the third+ times, we'll get more information each time to either confirm it's the same copy we're seeing again or identify duplicates (if we have a known location (book is shelved) and we encounter the same Work, then we'll automatically know it's a second+ Copy, but if we have any unshelved copies then it may be that copy, so simply get more information / confirm existing matches.)

# LibraCents MVP Plan

## Phase 1: Core Entity Migration
Convert existing Book-based system to Work/Edition/Copy model while maintaining current entry flow.

### 1.1 Database Migration
1. Create new models (Work, Edition, Copy)
2. Create migration path from existing Book records
3. Update Author relationships to Work level
4. Implement Edition-Work relationships
5. Implement Copy-Edition relationships

### 1.2 Entry Flow Updates
1. Maintain current author-first search
2. Modify book confirmation to identify Work
3. Add Edition selection/confirmation step
4. Add Copy creation step
5. Support "quick entry" (Work+Copy only) vs "detailed entry" (Work+Edition+Copy)

## Phase 2: Location Management
Implement physical organization system while keeping entry process efficient.

### 2.1 Location Setup
1. Location management interface
2. Room management within locations
3. Bookcase definition and shelf counting
4. Box creation and management
5. Book Group definition

### 2.2 Location Assignment
1. Add optional location selection to Copy creation
2. Support multiple detail levels:
   - Location only
   - Room specification
   - Bookcase selection
   - Shelf assignment
   - Box placement
3. Support bulk operations for boxes
4. Enable location changes/updates

## Phase 3: Search and Navigation
Enhance system usability while maintaining speed of entry.

### 3.1 Search Implementation
1. Work search (by title, author)
2. Edition search (by ISBN, publisher)
3. Copy search (by location, condition)
4. Box contents view
5. Location-based browsing

### 3.2 Navigation Improvements
1. Dashboard redesign for new entities
2. Location hierarchy navigation
3. Box management interface
4. Quick-entry vs detailed-entry mode switching
5. Bulk operations interface

## Phase 4: Data Management
Ensure reliable data handling and efficient operations.

### 4.1 OpenLibrary Integration
1. Update Work mapping
2. Add Edition mapping
3. Handle ISBN conflicts
4. Improve author disambiguation
5. Cache external data efficiently

### 4.2 Local Data Management
1. Implement Work merging
2. Handle Edition conflicts
3. Support Copy bulk updates
4. Location hierarchy validation
5. Box content tracking

## MVP Success Criteria
1. Users can quickly enter books (Work+Copy) with minimal clicks
2. Full Work/Edition/Copy model implemented
3. Location hierarchy supports all physical organization needs
4. Search works across all entity types
5. Bulk operations supported for boxes
6. External data properly mapped to internal model
7. All existing functionality maintained or improved

## Out of Scope for MVP
1. Mobile interface
2. Barcode scanning
3. Value tracking
4. Lending system
5. Remote backup
6. Multi-user support