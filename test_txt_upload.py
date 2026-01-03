"""
Quick test script to verify .txt file upload functionality for chat attachments
Run this after starting the Flask app to test the integration
"""
from blueprints.p2.models import VALID_FILE_TYPES, CREATABLE_FILE_TYPES, UPLOADABLE_FILE_TYPES
from utilities_main import get_file_type_from_extension, parse_document_for_chat
import tempfile
import os

def test_txt_in_valid_types():
    """Test that 'txt' is in VALID_FILE_TYPES"""
    print("Testing file type constants...")
    
    # Test that txt is in uploadable types
    assert 'txt' in UPLOADABLE_FILE_TYPES, "'txt' not found in UPLOADABLE_FILE_TYPES"
    print("✓ 'txt' is in UPLOADABLE_FILE_TYPES")
    
    # Test that txt is in valid types (union)
    assert 'txt' in VALID_FILE_TYPES, "'txt' not found in VALID_FILE_TYPES"
    print("✓ 'txt' is in VALID_FILE_TYPES")
    
    # Test separation of creatable vs uploadable
    assert 'proprietary_note' in CREATABLE_FILE_TYPES, "proprietary_note should be creatable"
    assert 'proprietary_note' not in UPLOADABLE_FILE_TYPES, "proprietary_note should not be uploadable"
    assert 'txt' in UPLOADABLE_FILE_TYPES, "txt should be uploadable"
    assert 'txt' not in CREATABLE_FILE_TYPES, "txt should not be creatable"
    print("✓ CREATABLE_FILE_TYPES and UPLOADABLE_FILE_TYPES are properly separated")
    
    # Test that VALID_FILE_TYPES is the union
    assert VALID_FILE_TYPES == CREATABLE_FILE_TYPES | UPLOADABLE_FILE_TYPES, \
        "VALID_FILE_TYPES should be union of CREATABLE and UPLOADABLE"
    print("✓ VALID_FILE_TYPES is correctly computed as union")
    
    # Check counts
    print(f"✓ CREATABLE_FILE_TYPES: {len(CREATABLE_FILE_TYPES)} types")
    print(f"✓ UPLOADABLE_FILE_TYPES: {len(UPLOADABLE_FILE_TYPES)} types")
    print(f"✓ VALID_FILE_TYPES: {len(VALID_FILE_TYPES)} types (union)")
    
    # Also check other text file types are in uploadable
    text_types = ['py', 'js', 'ts', 'html', 'css', 'yaml', 'json', 'env', 'md']
    for ftype in text_types:
        assert ftype in UPLOADABLE_FILE_TYPES, f"'{ftype}' not found in UPLOADABLE_FILE_TYPES"
    print(f"✓ All text file types present in UPLOADABLE_FILE_TYPES: {', '.join(text_types)}")


def test_file_type_detection():
    """Test that .txt extension maps to 'txt' type"""
    print("\nTesting file type detection...")
    
    test_cases = [
        ('sample.txt', 'txt'),
        ('README.TXT', 'txt'),
        ('notes.md', 'md'),
        ('script.py', 'py'),
        ('config.yaml', 'yaml'),
        ('data.json', 'json'),
    ]
    
    for filename, expected_type in test_cases:
        detected_type = get_file_type_from_extension(filename)
        assert detected_type == expected_type, f"Expected {expected_type} for {filename}, got {detected_type}"
        print(f"✓ {filename} -> {detected_type}")


def test_txt_parser():
    """Test that .txt files can be parsed correctly"""
    print("\nTesting .txt file parser...")
    
    # Create temporary .txt file with simple ASCII content
    temp_dir = tempfile.mkdtemp()
    test_file = os.path.join(temp_dir, 'test_sample.txt')
    test_content = "Hello, this is a test text file.\nIt has multiple lines.\nAnd that's all!"
    
    try:
        # Write test content
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        # Parse using the chat parser
        parsed_content, parse_method = parse_document_for_chat(test_file, 'txt')
        
        assert parse_method == 'text_read', f"Expected 'text_read' method, got {parse_method}"
        assert len(parsed_content) > 0, "Parsed content is empty"
        assert "test text file" in parsed_content, "Expected content not found in parsed text"
        
        print(f"✓ .txt file parsed successfully using '{parse_method}' method")
        print(f"✓ Parsed {len(parsed_content)} characters")
        print(f"✓ Content preview: {parsed_content[:60]}...")
        
    finally:
        # Clean up
        if os.path.exists(test_file):
            os.remove(test_file)
        os.rmdir(temp_dir)


def test_all_supported_extensions():
    """Print all supported file types by category"""
    print("\n" + "="*60)
    print("File Types by Category:")
    print("="*60)
    
    print("\nCreatable File Types (UI menu):")
    sorted_creatable = sorted(CREATABLE_FILE_TYPES)
    for i, ftype in enumerate(sorted_creatable, 1):
        print(f"  {i:2d}. {ftype}")
    print(f"  Total: {len(CREATABLE_FILE_TYPES)} types")
    
    print("\nUploadable File Types (attachments):")
    sorted_uploadable = sorted(UPLOADABLE_FILE_TYPES)
    for i, ftype in enumerate(sorted_uploadable, 1):
        print(f"  {i:2d}. {ftype}")
    print(f"  Total: {len(UPLOADABLE_FILE_TYPES)} types")
    
    print("\nAll Valid File Types (union):")
    sorted_all = sorted(VALID_FILE_TYPES)
    for i, ftype in enumerate(sorted_all, 1):
        print(f"  {i:2d}. {ftype}")
    print(f"  Total: {len(VALID_FILE_TYPES)} types")
    print("="*60)


if __name__ == '__main__':
    print("=" * 60)
    print("Testing .txt File Upload Integration")
    print("=" * 60)
    
    try:
        test_txt_in_valid_types()
        test_file_type_detection()
        test_txt_parser()
        test_all_supported_extensions()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Start the Flask app: python flask_app.py")
        print("2. Navigate to MioChat")
        print("3. Try uploading a .txt file as an attachment")
        print("4. Verify it appears in the attachment list")
        print("5. Try the 'Summarize' feature on the .txt file")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
