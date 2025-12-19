"""
Test script to verify that the _search_json_for_url function correctly finds
images in infinite whiteboard content_json structures.
"""

def _search_json_for_url(obj, url_path):
    """
    Recursively search JSON structure for a URL string.
    Returns True if found, False otherwise.
    """
    if obj is None:
        return False
    if isinstance(obj, str):
        return url_path in obj
    if isinstance(obj, dict):
        for key, value in obj.items():
            if _search_json_for_url(value, url_path):
                return True
    if isinstance(obj, list):
        for item in obj:
            if _search_json_for_url(item, url_path):
                return True
    return False


# Test cases
def test_search_json_for_url():
    """Test the _search_json_for_url function with various structures."""
    
    # Test 1: Simple string match
    assert _search_json_for_url("test /static/uploads/images/1_abc123.webp test", "/static/uploads/images/1_abc123.webp")
    print("✓ Test 1: Simple string match")
    
    # Test 2: Not found in string
    assert not _search_json_for_url("test image", "/static/uploads/images/1_abc123.webp")
    print("✓ Test 2: Not found in string")
    
    # Test 3: Infinite whiteboard structure with image
    infinite_board_content = {
        'objects': [
            {
                'id': 1,
                'type': 'stroke',
                'points': [[0, 0], [10, 10]],
                'color': '#000000'
            },
            {
                'id': 2,
                'type': 'image',
                'x': 100,
                'y': 100,
                'w': 200,
                'h': 150,
                'src': '/static/uploads/images/1_abc123.webp',
                'rotation': 0,
                'flipH': False,
                'flipV': False
            },
            {
                'id': 3,
                'type': 'text',
                'x': 300,
                'y': 300,
                'text': 'Hello World',
                'fontSize': 16
            }
        ],
        'nextObjectId': 4,
        'viewport': {
            'x': 0,
            'y': 0,
            'scale': 1.0
        }
    }
    assert _search_json_for_url(infinite_board_content, "/static/uploads/images/1_abc123.webp")
    print("✓ Test 3: Found in infinite whiteboard structure")
    
    # Test 4: Image not in infinite whiteboard
    assert not _search_json_for_url(infinite_board_content, "/static/uploads/images/2_xyz789.webp")
    print("✓ Test 4: Not found in infinite whiteboard structure")
    
    # Test 5: Multiple images in infinite whiteboard
    multi_image_content = {
        'objects': [
            {
                'id': 1,
                'type': 'image',
                'src': '/static/uploads/images/1_abc123.webp'
            },
            {
                'id': 2,
                'type': 'image',
                'src': '/static/uploads/images/1_def456.webp'
            },
            {
                'id': 3,
                'type': 'image',
                'src': '/static/uploads/images/1_ghi789.webp'
            }
        ]
    }
    assert _search_json_for_url(multi_image_content, "/static/uploads/images/1_abc123.webp")
    assert _search_json_for_url(multi_image_content, "/static/uploads/images/1_def456.webp")
    assert _search_json_for_url(multi_image_content, "/static/uploads/images/1_ghi789.webp")
    assert not _search_json_for_url(multi_image_content, "/static/uploads/images/1_notfound.webp")
    print("✓ Test 5: Multiple images in infinite whiteboard")
    
    # Test 6: Nested structures
    nested_content = {
        'metadata': {
            'description': 'Contains image /static/uploads/images/1_nested.webp in description'
        }
    }
    assert _search_json_for_url(nested_content, "/static/uploads/images/1_nested.webp")
    print("✓ Test 6: Nested structure with image in description")
    
    # Test 7: Empty/None cases
    assert not _search_json_for_url(None, "/static/uploads/images/1_abc123.webp")
    assert not _search_json_for_url({}, "/static/uploads/images/1_abc123.webp")
    assert not _search_json_for_url([], "/static/uploads/images/1_abc123.webp")
    print("✓ Test 7: Empty/None cases")
    
    # Test 8: Regular whiteboard structure (legacy)
    regular_board_content = {
        'elements': [
            {
                'type': 'image',
                'url': '/static/uploads/images/1_board.webp',
                'x': 50,
                'y': 50
            }
        ],
        'background': 'white'
    }
    assert _search_json_for_url(regular_board_content, "/static/uploads/images/1_board.webp")
    print("✓ Test 8: Regular whiteboard structure")
    
    print("\n✅ All tests passed! The _search_json_for_url function works correctly.")


if __name__ == '__main__':
    test_search_json_for_url()
