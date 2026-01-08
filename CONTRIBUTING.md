# Contributing to Lead Dashboard

Thank you for your interest in contributing to Lead Dashboard! This document provides guidelines and instructions for contributing.

## 🚀 Getting Started

1. **Fork the repository** and clone your fork
2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install dependencies**:
   ```bash
   cd lead_dashboard
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```
4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```
5. **Initialize the database**:
   ```bash
   flask db upgrade
   ```

## 📝 Development Workflow

### 1. Create a Branch

Create a feature branch from `main`:
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write clean, readable code
- Follow PEP 8 style guidelines
- Add docstrings to functions and classes
- Update documentation as needed

### 3. Write Tests

- Add tests for new features
- Ensure all tests pass: `pytest`
- Aim for >70% test coverage

### 4. Commit Changes

Use clear, descriptive commit messages:
```bash
git commit -m "Add feature: description of what you added"
```

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## 🧪 Testing

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=lead_dashboard --cov-report=html
```

## 📋 Code Style

We use:
- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting

Format code before committing:
```bash
black .
isort .
flake8 .
```

Or use pre-commit hooks (automatically runs on commit):
```bash
pre-commit install
```

## 🐛 Reporting Bugs

When reporting bugs, please include:
- Description of the bug
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (OS, Python version, etc.)
- Screenshots if applicable

## 💡 Suggesting Features

Feature suggestions are welcome! Please:
- Check if the feature already exists
- Describe the use case
- Explain how it would benefit users
- Consider implementation complexity

## 📚 Documentation

- Update README.md if needed
- Add docstrings to new functions/classes
- Update API documentation for API changes
- Add examples for new features

## 🔒 Security

If you discover a security vulnerability:
- **DO NOT** open a public issue
- Email security concerns privately
- We'll address it promptly

## ✅ Pull Request Checklist

Before submitting a PR, ensure:
- [ ] Code follows style guidelines
- [ ] Tests are added/updated and passing
- [ ] Documentation is updated
- [ ] Commit messages are clear
- [ ] No merge conflicts
- [ ] All CI checks pass

## 📞 Questions?

Feel free to open an issue for questions or reach out to maintainers.

Thank you for contributing! 🎉
