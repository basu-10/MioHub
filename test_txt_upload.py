"""
Quick test script to verify .txt file upload functionality for chat attachments
Run this after starting the Flask app to test the integration
"""
from blueprints.p2.models import VALID_FILE_TYPES
from utilities_main import get_file_type_from_extension, parse_document_for_chat
import tempfile
import os

def test_txt_in_valid_types():
    """Test that 'txt' is in VALID_FILE_TYPES"""
    print("Testing VALID_FILE_TYPES...")
    assert 'txt' in VALID_FILE_TYPES, "'txt' not found in VALID_FILE_TYPES"
    print("✓ 'txt' is in VALID_FILE_TYPES")
    
    # Also check other text file types
    text_types = ['py', 'js', 'ts', 'html', 'css', 'yaml', 'json', 'env', 'md']
    for ftype in text_types:
        assert ftype in VALID_FILE_TYPES, f"'{ftype}' not found in VALID_FILE_TYPES"
    print(f"✓ All text file types present: {', '.join(text_types)}")


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
    """Print all supported file types"""
    print("\nAll supported file types:")
    sorted_types = sorted(VALID_FILE_TYPES)
    for i, ftype in enumerate(sorted_types, 1):
        print(f"  {i:2d}. {ftype}")
    print(f"\nTotal: {len(VALID_FILE_TYPES)} file types supported")


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
