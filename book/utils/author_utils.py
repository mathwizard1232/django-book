def format_primary_name(author_name, ol_name):
    """
    Format primary name to show pen name relationship when relevant.
    If the OpenLibrary name differs significantly from author name, format as "FirstName 'PenName' LastName"
    
    Args:
        author_name: The name we searched for/display name (e.g. "Max Brand")
        ol_name: The name from OpenLibrary (e.g. "Frederick Schiller Faust")
    """
    # Clean up author_name (remove work count if present)
    if '(' in author_name:
        author_name = author_name.split('(')[0].strip()
    
    # If names are similar enough, just use the OpenLibrary name
    # TODO: Make this more sophisticated
    # We need to ignore cases where it's just like "JRR Tolkien" vs "John Ronald Reuel Tolkien" etc
    if author_name.lower() == ol_name.lower():
        return ol_name
        
    # Otherwise, it's a pen name situation - extract first and last name
    first, *_, last = ol_name.split()
    return f"{first} '{author_name}' {last}" 