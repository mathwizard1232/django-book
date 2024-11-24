# Book Entity Definitions

## Overview
This document defines the three core entities in our library management system that represent different aspects of what we colloquially call a "book": Works, Editions, and Copies.

## Work
A Work represents the core intellectual content created by an author(s), independent of its physical form or presentation.

### Characteristics
- Unique identifier
- Title
- Author(s)
- Original publication date
- Type (novel, short story, anthology, etc.)
- Component Works (for collections/anthologies)

### Relationships
- One Work can have many Editions
- A Work can contain other Works (for collections)
- A Work is created by one or more Authors

## Edition
An Edition represents a specific published version of a Work.

### Characteristics
- Unique identifier
- Publisher
- Publication date
- Language
- Format (hardcover, paperback, ebook, etc.)
- ISBN (0 or 1)
- Cover art
- Page count
- Physical dimensions

### Relationships
- Each Edition represents exactly one Work
- One Edition can have many Copies
- An Edition may have zero or one ISBN

## Copy
A Copy represents a physical instance of an Edition owned by someone.

### Characteristics
- Unique identifier (could be RFID, barcode, or system-generated)
- Condition
- Acquisition date
- Location (shelf, room, etc.)
- Purchase price (optional)
- Notes

### Relationships
- Each Copy represents exactly one Edition
- A Copy is owned by one Person/Library
- A Copy can be loaned to one Person at a time

## Implementation Considerations
1. **Local vs External Data**
   - Editions can be sourced from external databases (OpenLibrary); Works are our concept
   - Local database is maintained of anything in the user's library
   - Copies are always stored locally

2. **Search Optimization**
   - Author-first search pattern for efficient Work location
   - ISBN lookup for quick Edition identification (when paired with barcode scanning)
   - Local Copy tracking with flexible tagging/notes system

3. **Data Integrity**
   - Handle ISBN collisions gracefully
   - Maintain clear relationships between Works/Editions/Copies
   - Support merging of duplicate records