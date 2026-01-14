# Flask Web Application

Flask web application with modular architecture featuring three main products:
- Product1: Calculator functionality  
- Product2: MioWord document system (MioWord, MioBoard, and MioWork)
- Product3: AI chatbot system with Groq integration

Originally deployed on PythonAnywhere, now migrated to MX LINUX local development.

## Quick Start

1. Copy configuration template:
   ```
   copy config.yaml.template config.yaml
   ```

2. Edit config.yaml with your database and API credentials

3. Run the project setup:
   ```
   start_project.bat
   ```

4. Initialize the database:
   ```
   python init_db.py
   ```

5. Start the application:
   ```
   python flask_app.py
   ```

## Configuration

The application uses YAML configuration instead of .env files. See:
- `config.yaml.template` - Template with example values
- `YAML_MIGRATION.md` - Migration guide from .env to YAML
- `.github/copilot-instructions.md` - Detailed project documentation

## Testing

Run configuration tests:
```
python test_yaml_config.py
python tesst_env.py
python test_db_connection.py
```

See https://help.pythonanywhere.com/ (or click the "Help" link at the top
right) for help on how to use PythonAnywhere, including tips on copying and
pasting from consoles, and writing your own web applications.
