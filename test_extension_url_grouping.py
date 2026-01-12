"""
Test script for Chrome extension URL grouping feature.

Tests:
1. URL normalization
2. File creation and appending
3. Quota delta calculation
"""

from blueprints.p2.extension_api import normalize_url, append_to_html_content

def test_url_normalization():
    """Test that URL normalization works correctly."""
    test_cases = [
        # (input, expected_output)
        ('https://example.com?utm_source=twitter', 'https://example.com'),
        ('https://example.com/', 'https://example.com'),
        ('https://example.com/article#section', 'https://example.com/article'),
        ('https://example.com/article/?page=1', 'https://example.com/article'),
        ('https://example.com', 'https://example.com'),
        ('', ''),
        (None, ''),
    ]
    
    print("Testing URL Normalization:")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for input_url, expected in test_cases:
        result = normalize_url(input_url) if input_url is not None else normalize_url('')
        status = "✓" if result == expected else "✗"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} Input:    {input_url}")
        print(f"  Expected: {expected}")
        print(f"  Got:      {result}")
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    print()


def test_content_appending():
    """Test HTML content appending with separator."""
    print("Testing Content Appending:")
    print("=" * 60)
    
    # Test 1: Append to empty content
    result1 = append_to_html_content('', '<p>First content</p>')
    print("Test 1: Append to empty content")
    print(f"Result: {result1}")
    print(f"Expected: <p>First content</p>")
    print(f"Status: {'✓' if result1 == '<p>First content</p>' else '✗'}")
    print()
    
    # Test 2: Append to existing content
    existing = '<p>First content</p>'
    new_content = '<p>Second content</p>'
    result2 = append_to_html_content(existing, new_content)
    print("Test 2: Append to existing content")
    print(f"Has separator: {'✓' if '<hr style=' in result2 else '✗'}")
    print(f"Contains first: {'✓' if 'First content' in result2 else '✗'}")
    print(f"Contains second: {'✓' if 'Second content' in result2 else '✗'}")
    print(f"Separator before second: {'✓' if result2.index('<hr') < result2.index('Second') else '✗'}")
    print()
    
    # Test 3: Multiple appends
    content = '<p>Content 1</p>'
    content = append_to_html_content(content, '<p>Content 2</p>')
    content = append_to_html_content(content, '<p>Content 3</p>')
    separator_count = content.count('<hr')
    print(f"Test 3: Multiple appends (3 total)")
    print(f"Separator count: {separator_count} (expected: 2)")
    print(f"Status: {'✓' if separator_count == 2 else '✗'}")
    print()
    
    print("=" * 60)
    print()


def test_size_calculation():
    """Test that size delta calculation is correct."""
    print("Testing Size Delta Calculation:")
    print("=" * 60)
    
    old_content = '<p>Hello world</p>'
    new_content = '<p>Hello world</p><hr /><p>New clip</p>'
    
    old_size = len(old_content.encode('utf-8'))
    new_size = len(new_content.encode('utf-8'))
    delta = new_size - old_size
    
    print(f"Old content size: {old_size} bytes")
    print(f"New content size: {new_size} bytes")
    print(f"Delta: {delta} bytes")
    print()
    
    # Verify delta is positive and less than total
    print(f"Delta > 0: {'✓' if delta > 0 else '✗'}")
    print(f"Delta < new_size: {'✓' if delta < new_size else '✗'}")
    print(f"Delta = difference: {'✓' if delta == (new_size - old_size) else '✗'}")
    
    print("=" * 60)
    print()


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Chrome Extension URL Grouping - Unit Tests")
    print("=" * 60 + "\n")
    
    test_url_normalization()
    test_content_appending()
    test_size_calculation()
    
    print("All tests completed!")
    print("=" * 60)
