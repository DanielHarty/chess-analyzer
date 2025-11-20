import asyncio

async def extract_pgn_content(file_obj) -> tuple[str, str]:
    """
    Extract and decode content from an uploaded file object.
    
    Args:
        file_obj: The file object from NiceGUI upload event or similar.
        
    Returns:
        Tuple of (filename, content_string)
        
    Raises:
        ValueError: If content cannot be extracted.
    """
    filename = getattr(file_obj, 'name', 'unknown_file')

    # Try official NiceGUI APIs first
    if hasattr(file_obj, 'read'):
        # File-like object with read method (async in NiceGUI)
        content = (await file_obj.read()).decode('utf-8')
        return filename, content
    elif hasattr(file_obj, 'content'):
        # Direct content attribute (bytes)
        if isinstance(file_obj.content, bytes):
            content = file_obj.content.decode('utf-8')
        else:
            content = str(file_obj.content)
        return filename, content
    elif hasattr(file_obj, '_data'):
        # Fallback to private attribute (current implementation)
        content = file_obj._data.decode('utf-8')
        return filename, content
    else:
        raise ValueError("Unable to extract content from uploaded file")

