Current status: We've updated models to distinguish Work/Edition/Copy, but we want to leave input as
Work-only for now. We're going to add Location management next.

# Location Management UI/UX Plan

## 1. Location Setup Interface
1. Simple list/table of Locations
2. Add Location button -> modal form with:
   - Name (e.g., "Home Office", "Storage Unit")
   - Description (optional)
   - Type (Room, Box, Shelf, etc.)
   - Parent Location (optional)

## 2. Work Entry Flow Integration
1. Add optional Location field to Work entry form
2. Quick dropdown of recent/favorite locations
3. "Add New Location" option within dropdown
4. Keep it optional - don't interrupt fast entry flow

## 3. Location Views
1. Hierarchical tree view of all locations
2. List of Works by location
3. Simple drag-and-drop to move Works between locations
4. Bulk selection/move operations

## Success Criteria
- Location entry doesn't slow down Work entry
- Users can quickly find where a Work is stored
- Easy to reorganize Works between locations
- Support for both organized (shelves) and temporary (boxes) storage

## Future Enhancements
- Barcode/QR codes for locations
- Mobile-friendly location scanning
- Location history tracking
- Space management/shelf capacity