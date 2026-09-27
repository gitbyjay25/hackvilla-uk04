# Contributing to Nexarch SDK

Thank you for your interest in contributing to Nexarch SDK!

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/nexarch/nexarch-sdk.git
cd nexarch-sdk
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install in development mode:
```bash
pip install -e ".[dev]"
```

4. Run tests:
```bash
pytest
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints wherever possible
- Add docstrings to all public functions and classes
- Format code with `black`:
  ```bash
  black nexarch/
  ```
- Lint with `ruff`:
  ```bash
  ruff check nexarch/
  ```

## Testing

- Write tests for all new features
- Ensure all tests pass before submitting PR
- Aim for >80% code coverage

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## Questions?

Open an issue or reach out to the maintainers.
