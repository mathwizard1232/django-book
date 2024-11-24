# Location Definitions

## Overview
This document defines the hierarchical structure of physical locations in our library management system, from high-level locations down to specific shelves, as well as the concept of logical groupings of books.

## Location Hierarchy

### Location
Represents a distinct physical building or storage space.

#### Characteristics
- Unique identifier
- Name
- Address (optional)
- Type (house, storage unit, cabin, etc.)
- Notes

#### Relationships
- A Location can contain multiple Rooms
- A Location can contain Bookcases directly (for simple spaces)

### Room
Represents a distinct space within a Location.

#### Characteristics
- Unique identifier
- Name
- Floor/level (optional)
- Notes

#### Relationships
- A Room belongs to exactly one Location
- A Room can contain multiple Bookcases

### Bookcase
Represents a physical storage unit for books.

#### Characteristics
- Unique identifier
- Name/identifier (e.g., "Living Room North Bookcase")
- Number of shelves
- Notes

#### Relationships
- A Bookcase belongs to either one Room or one Location
- A Bookcase contains multiple Shelves
- A Bookcase can be associated with one or more Book Groups

### Shelf
Represents a single shelf within a Bookcase.

#### Characteristics
- Unique identifier
- Position number (1-based, counting from top)
- Notes

#### Relationships
- A Shelf belongs to exactly one Bookcase
- A Shelf can be associated with one or more Book Groups

### Box
Represents a container for books that can be moved as a unit.

#### Characteristics
- Unique identifier
- Label/name
- Dimensions (optional)
- Status (sealed/unsealed)
- Notes

#### Relationships
- A Box belongs to either one Room or one Location
- A Box contains multiple Copies
- A Box can be associated with one or more Book Groups

## Book Groups
Represents a logical collection of books that share a common organization scheme.

### Characteristics
- Unique identifier
- Name
- Organization scheme (e.g., "Alphabetical by author", "By publication date")
- Description
- Notes

### Relationships
- A Book Group can span multiple Bookcases and/or Shelves
- Books (Copies) can be assigned to a Book Group

## Implementation Considerations

1. **Location Assignment**
   - Copies can be marked as "unshelved" when first entered
   - Location can be specified at various levels of detail:
     - Just the Location ("at the cabin")
     - Room level ("master bedroom")
     - Bookcase level ("living room north bookcase")
     - Shelf level ("living room north bookcase, shelf 3")
     - Box ("Box 12: Sci-Fi Paperbacks")
     - Book Group ("Vintage Sci-Fi novels")

2. **Book Entry Modes**
   - Simple: Work identification + Copy creation (unshelved)
   - Advanced: Include location specification during entry
   - Support bulk operations for entering multiple books in same location

3. **Flexibility**
   - Support both simple (single-room) and complex (multi-room) locations
   - Allow for temporary/transitional locations
   - Support reorganization and movement of books between locations

4. **Search and Retrieval**
   - Enable finding books by any level of location hierarchy
   - Support finding books by Book Group across multiple physical locations
   - Quick lookup of all books in a given Location/Room/Bookcase/Shelf

5. **Bulk Operations**
   - Support moving entire Boxes between Locations/Rooms
   - Track Box contents as a unit during moves
   - Allow for easy inventory of Box contents
   - Support converting between Box and Shelf storage (unpacking/packing)