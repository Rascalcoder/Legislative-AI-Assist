# Contributing to Legislative AI Assist

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow

## How to Contribute

### 1. Fork & Clone

```bash
git clone https://github.com/your-username/legislative-ai-assist.git
cd legislative-ai-assist
git remote add upstream https://github.com/original-org/legislative-ai-assist.git
```

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

Branch naming:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/improvements

### 3. Make Changes

#### Backend (Python)
- Follow PEP 8 style guide
- Add type hints
- Write docstrings
- Add tests for new features

```python
def example_function(param: str) -> dict:
    """
    Brief description.
    
    Args:
        param: Description of parameter
        
    Returns:
        Description of return value
    """
    pass
```

#### Frontend (JavaScript)
- Use ES6+ features
- Follow existing code style
- Add JSDoc comments for complex functions
- Keep functions small and focused

```javascript
/**
 * Brief description
 * @param {string} param - Description
 * @returns {Promise<Object>} Description
 */
async function exampleFunction(param) {
    // Implementation
}
```

### 4. Test Your Changes

#### Backend Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_chat.py
```

#### Frontend Tests
```bash
cd frontend

# Build to verify no errors
npm run build

# Test locally
npm run dev
```

### 5. Commit Changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "feat: add support for multilingual queries

- Implement language detection
- Add Slovak translation support
- Update prompt templates"
```

Commit message format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `style:` - Code style (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

### 6. Push & Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear title describing the change
- Description of what changed and why
- Reference any related issues (#123)
- Screenshots for UI changes

## Development Guidelines

### Backend Architecture

```
api/          # FastAPI routes
services/     # Business logic
pipeline/     # AI pipeline (router, retrieval, generate)
config/       # Configuration files
```

**Key Principles:**
- Separation of concerns
- Keep routes thin (delegate to services)
- Use dependency injection
- Handle errors gracefully

### Frontend Architecture

**Structure:**
- Single-page application (SPA)
- View switching via JavaScript
- Event-driven architecture
- API calls via fetch

**Best Practices:**
- Keep functions pure when possible
- Use async/await for API calls
- Handle loading and error states
- Provide user feedback (toasts)

### Configuration

All configuration in `config/*.json`:
- `models.json` - LLM models and providers
- `search.json` - Search parameters
- `sources.json` - Legal sources
- `prompts.json` - System prompts

**Never hardcode:**
- API keys
- Model names
- Search parameters
- URLs

### Code Quality

#### Python
```bash
# Linting
flake8 .

# Type checking
mypy . --ignore-missing-imports

# Formatting
black .
```

#### JavaScript
```bash
# Linting (if you add ESLint)
npm run lint

# Formatting (if you add Prettier)
npm run format
```

## What to Contribute

### High Priority
- 🐛 Bug fixes
- 📚 Documentation improvements
- 🧪 Test coverage
- ♿ Accessibility improvements
- 🌍 Translations

### Ideas Welcome
- ✨ New features (discuss first in issues)
- 🎨 UI/UX improvements
- ⚡ Performance optimizations
- 🔒 Security enhancements

### Areas Needing Help
- Unit tests for services
- Integration tests for API endpoints
- Slovak/Hungarian translations
- Documentation examples
- Performance benchmarks

## Review Process

1. **Automated Checks** - CI must pass
   - Tests
   - Linting
   - Build validation
   - Security scan

2. **Code Review** - At least 1 approval required
   - Code quality
   - Follows guidelines
   - Tests included
   - Documentation updated

3. **Merge** - Squash and merge to main

## Questions?

- Open an issue for discussion
- Tag maintainers for urgent questions
- Check existing issues/PRs first

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing! 🎉**




