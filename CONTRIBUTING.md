# Contributing to Meal Mind

Thank you for your interest in contributing to Meal Mind! This document provides guidelines and instructions for contributing to the project.

## 🍴 Forking and Syncing

### Forking the Repository

1. Click the "Fork" button at the top right of the repository page
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR-USERNAME/MealMind.git
   cd MealMind
   ```

### Syncing Your Fork

To keep your fork up-to-date with the upstream repository, you have several options:

#### Option 1: Using GitHub's Sync Fork Button

GitHub provides a "Sync fork" button on your fork's page. Simply:
1. Go to your fork on GitHub
2. Click the "Sync fork" button
3. Click "Update branch"

**Note**: This button is always available since this repository doesn't contain GitHub Actions workflows that could pose security concerns.

#### Option 2: Using Git Commands

If you prefer using the command line:

1. Add the upstream repository (only needed once):
   ```bash
   git remote add upstream https://github.com/ghantasala-sr/MealMind.git
   ```

2. Verify the remote:
   ```bash
   git remote -v
   ```

3. Fetch upstream changes:
   ```bash
   git fetch upstream
   ```

4. Merge upstream changes into your branch:
   ```bash
   git checkout main
   git merge upstream/main
   ```

5. Push updates to your fork:
   ```bash
   git push origin main
   ```

#### Option 3: Using GitHub CLI

If you have the GitHub CLI installed:

```bash
gh repo sync YOUR-USERNAME/MealMind -b main
```

## 🔧 Development Setup

1. **Fork and Clone**: Follow the forking instructions above

2. **Set up the development environment**:
   ```bash
   cd meal_mind_streamlit
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   Create a `.env` file in the `meal_mind_streamlit` directory:
   ```env
   RAPIDAPI_KEY=your_rapidapi_key_here
   RAPIDAPI_HOST=nutrition-calculator.p.rapidapi.com
   ```

## 🎯 Making Contributions

### Creating a Branch

Always create a new branch for your changes:

```bash
git checkout -b feature/your-feature-name
```

### Making Changes

1. Make your changes in the appropriate files
2. Test your changes thoroughly
3. Ensure code follows the existing style
4. Update documentation if needed

### Submitting a Pull Request

1. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Go to the original repository and create a Pull Request
3. Provide a clear description of your changes
4. Link any related issues

## 📝 Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions focused and small

## 🧪 Testing

Before submitting a PR:
1. Test the application locally
2. Ensure no existing functionality is broken
3. Test edge cases

## 💬 Communication

- Use GitHub Issues for bug reports and feature requests
- Be respectful and constructive in discussions
- Provide detailed information when reporting issues

## 📄 License

By contributing to Meal Mind, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing to Meal Mind! 🎉
