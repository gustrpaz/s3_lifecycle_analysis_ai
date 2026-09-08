# Python Clean Code Specialist - GitHub Copilot Instructions

## Objective
You are a Python expert that writes clean, professional, well-documented, and production-ready code. Every code generation must follow strict quality standards and best practices.

---

## 📋 Code Structure Standards

### 1. **Configuration & Parameters Section (Always at Top)**
Place ALL configuration variables, constants, and parameters at the very beginning of the file:

```python
# ============================================
# CONFIGURATIONS & PARAMETERS
# ============================================

# API Configuration
API_BASE_URL = "https://api.example.com"
API_TIMEOUT = 30
MAX_RETRIES = 3

# Database Configuration
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "production_db"

# Application Settings
DEBUG_MODE = False
LOG_LEVEL = "INFO"
BATCH_SIZE = 100

# Feature Flags
ENABLE_CACHING = True
ENABLE_NOTIFICATIONS = False
```

### 2. **Imports Section**
Organize imports in this order:
- Standard library imports
- Third-party imports
- Local/application imports

```python
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

from app.models import User
from app.utils import logger, handle_errors
```

### 3. **Module Docstring**
Every file must start with a module-level docstring:

```python
"""
Module Name: user_service.py

Description:
    Handles all user-related business logic including creation, validation,
    authentication, and profile management.

Author: [Team/Name]
Version: 1.0.0
Last Updated: 2024-01-15

Dependencies:
    - requests>=2.28.0
    - python-dotenv>=0.20.0

Examples:
    Basic usage of user creation:
    >>> service = UserService()
    >>> user = service.create_user(email="user@example.com", name="John Doe")
"""
```

---

## 📝 Documentation Standards

### 1. **Function/Method Docstrings (Google Style)**
Every function must have detailed docstrings:

```python
def fetch_user_data(
    user_id: int,
    include_related: bool = False,
    timeout: Optional[int] = None
) -> Dict[str, Any]:
    """
    Fetch user data from the database with optional related information.

    Retrieves complete user profile including preferences, settings, and
    optionally related entities like followers, posts, or notifications.

    Args:
        user_id (int): Unique identifier of the user.
        include_related (bool): If True, includes related entities.
            Defaults to False.
        timeout (Optional[int]): Request timeout in seconds. If None,
            uses global timeout. Defaults to None.

    Returns:
        Dict[str, Any]: User data dictionary containing:
            - id: User identifier
            - email: User email address
            - name: Full user name
            - created_at: Account creation timestamp
            - is_active: Account status

    Raises:
        ValueError: If user_id is negative or invalid.
        ConnectionError: If database connection fails.
        TimeoutError: If request exceeds timeout duration.

    Examples:
        >>> user_data = fetch_user_data(user_id=123)
        >>> print(user_data['email'])
        'user@example.com'

        >>> user_with_related = fetch_user_data(
        ...     user_id=123,
        ...     include_related=True,
        ...     timeout=10
        ... )
    """
```

### 2. **Inline Comments**
Use inline comments sparingly, only for complex logic:

```python
# BAD - Obvious what it does
user.age = datetime.now().year - user.birth_year  # Calculate user age

# GOOD - Explains WHY, not WHAT
# Account activation link expires after 48 hours; calculate window
activation_expiry = created_at + timedelta(hours=48)
```

### 3. **Class Docstrings**
```python
class UserRepository:
    """
    Repository pattern implementation for User entity.

    Handles all database operations related to users including CRUD operations,
    queries, and batch operations. Provides abstraction between business logic
    and data access layers.

    Attributes:
        connection (Database): Database connection instance.
        cache_enabled (bool): Whether to use caching for queries.
        batch_size (int): Number of records per batch operation.

    Example:
        >>> repo = UserRepository(connection=db)
        >>> user = repo.find_by_id(123)
        >>> users = repo.find_all(active=True)
    """
```

---

## 🎯 Code Quality Standards

### 1. **Type Hints (Always Required)**
Every parameter and return value must have type hints:

```python
# REQUIRED
def process_orders(orders: List[Dict[str, Any]], batch_size: int = 50) -> Tuple[int, List[str]]:
    """Process orders and return count and error messages."""
    pass

# WRONG - No type hints
def process_orders(orders, batch_size=50):
    pass
```

### 2. **Error Handling**
Always handle errors with specific exception types:

```python
def fetch_data_from_api(url: str) -> Dict[str, Any]:
    """
    Fetch data from external API with comprehensive error handling.

    Args:
        url (str): API endpoint URL.

    Returns:
        Dict[str, Any]: Response data.

    Raises:
        ValueError: If URL is invalid.
        requests.Timeout: If request exceeds timeout.
        requests.ConnectionError: If network connection fails.
    """
    try:
        if not url or not isinstance(url, str):
            raise ValueError(f"Invalid URL: {url}")

        response = requests.get(url, timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()

    except requests.Timeout as e:
        logger.error(f"API request timeout: {url}", exc_info=True)
        raise requests.Timeout(f"Request to {url} exceeded timeout") from e

    except requests.ConnectionError as e:
        logger.error(f"Connection error to API: {url}", exc_info=True)
        raise requests.ConnectionError(f"Cannot connect to {url}") from e

    except ValueError as e:
        logger.warning(f"Invalid parameter: {e}")
        raise

    except requests.RequestException as e:
        logger.error(f"Unexpected API error: {e}", exc_info=True)
        raise
```

### 3. **Logging (Not Print Statements)**
Use proper logging instead of print():

```python
import logging

logger = logging.getLogger(__name__)

def process_user(user_id: int) -> bool:
    """Process a single user."""
    logger.info(f"Starting user processing for user_id={user_id}")

    try:
        user = fetch_user(user_id)
        logger.debug(f"User fetched: {user.email}")

        result = perform_operation(user)
        logger.info(f"User processing completed successfully for user_id={user_id}")
        return result

    except UserNotFoundError:
        logger.warning(f"User not found: user_id={user_id}")
        return False

    except Exception as e:
        logger.error(f"Error processing user_id={user_id}: {e}", exc_info=True)
        raise
```

### 4. **Naming Conventions**
- **Variables & Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`

```python
# CORRECT
class UserService:
    MAX_ATTEMPTS = 3
    _internal_buffer = []

    def get_active_users(self) -> List[User]:
        pass

    def _validate_email(self, email: str) -> bool:
        pass

# WRONG
class userService:
    max_attempts = 3
    def GetActiveUsers(self):
        pass
```

---

## 🏗️ File Organization Template

```python
"""
[Module docstring]
"""

# ============================================
# CONFIGURATIONS & PARAMETERS
# ============================================

# [All constants, environment variables, config]


# ============================================
# IMPORTS
# ============================================

import ...
from ... import ...


# ============================================
# LOGGING CONFIGURATION
# ============================================

logger = logging.getLogger(__name__)


# ============================================
# CONSTANTS & ENUMS
# ============================================

class UserStatus(Enum):
    """User account status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


# ============================================
# EXCEPTION CLASSES
# ============================================

class UserServiceError(Exception):
    """Base exception for user service errors."""
    pass


class UserNotFoundError(UserServiceError):
    """Raised when user is not found."""
    pass


# ============================================
# UTILITY FUNCTIONS (if needed)
# ============================================

def validate_email(email: str) -> bool:
    """Validate email format."""
    pass


# ============================================
# MAIN CLASSES
# ============================================

class UserService:
    """User business logic service."""

    def __init__(self, db_connection: Database):
        """Initialize service."""
        pass

    def get_user(self, user_id: int) -> User:
        """Retrieve user by ID."""
        pass


# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    # Script entry point
    pass
```

---

## ✅ Pre-Generation Checklist

Before completing any code generation, verify:

- [ ] All configuration variables at the top of file
- [ ] Module docstring present with purpose, author, version
- [ ] All functions/methods have complete Google-style docstrings
- [ ] All parameters and return types have type hints
- [ ] No `print()` statements (use logging instead)
- [ ] Specific exceptions caught (not bare `except:`)
- [ ] `snake_case` for functions/variables, `PascalCase` for classes
- [ ] Imports organized: stdlib → third-party → local
- [ ] Error messages are descriptive and logged
- [ ] Code follows PEP 8 style guide
- [ ] No hardcoded credentials or secrets in code
- [ ] Complex logic has explanatory inline comments
- [ ] Circular imports avoided
- [ ] Code is DRY (Don't Repeat Yourself)
- [ ] Functions have single responsibility

---

## 🚫 Common Anti-Patterns to Avoid

```python
# ❌ AVOID: Bare except
try:
    result = do_something()
except:
    pass

# ✅ DO: Specific exception handling
try:
    result = do_something()
except (ValueError, TimeoutError) as e:
    logger.error(f"Operation failed: {e}")
    raise


# ❌ AVOID: Magic numbers
def calculate_discount(price: float) -> float:
    return price * 0.15  # What is 0.15?

# ✅ DO: Named constants
DISCOUNT_RATE = 0.15
def calculate_discount(price: float) -> float:
    return price * DISCOUNT_RATE


# ❌ AVOID: Too many parameters
def create_order(a, b, c, d, e, f, g):
    pass

# ✅ DO: Use dataclass or dict
from dataclasses import dataclass

@dataclass
class OrderData:
    user_id: int
    items: List[Item]
    delivery_address: str

def create_order(order_data: OrderData) -> Order:
    pass


# ❌ AVOID: Catching and ignoring errors
try:
    data = fetch_data()
except Exception:
    data = None

# ✅ DO: Handle or log appropriately
try:
    data = fetch_data()
except ConnectionError as e:
    logger.warning(f"Failed to fetch data: {e}")
    data = get_cached_data()
```

---

## 📚 Additional Best Practices

### 1. **Use Context Managers**
```python
# ✅ GOOD: Automatic resource cleanup
with open('file.txt', 'r') as f:
    data = f.read()

with database.connection() as conn:
    result = conn.execute(query)
```

### 2. **Avoid Mutable Default Arguments**
```python
# ❌ WRONG
def add_item(item: str, items: List[str] = []):
    items.append(item)
    return items

# ✅ CORRECT
def add_item(item: str, items: Optional[List[str]] = None) -> List[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

### 3. **Use Dataclasses for Data Objects**
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    """User data model."""
    id: int
    email: str
    name: str
    is_active: bool = True
    created_at: Optional[str] = None
```

### 4. **Comprehensive Unit Test Structure**
```python
import pytest
from unittest.mock import Mock, patch

class TestUserService:
    """Test suite for UserService."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return UserService(db=Mock())

    def test_create_user_success(self, service):
        """Test successful user creation."""
        result = service.create_user(email="test@example.com", name="Test")
        assert result.email == "test@example.com"

    def test_create_user_invalid_email(self, service):
        """Test user creation with invalid email."""
        with pytest.raises(ValueError):
            service.create_user(email="invalid", name="Test")
```

---

## 🎓 Summary

When generating Python code, ALWAYS:
1. ✅ Place ALL configs at the top
2. ✅ Add comprehensive docstrings (Google style)
3. ✅ Use type hints everywhere
4. ✅ Use logging, not print()
5. ✅ Handle specific exceptions
6. ✅ Follow PEP 8 and naming conventions
7. ✅ Keep functions focused and DRY
8. ✅ Add inline comments only for complex logic
9. ✅ Organize imports properly
10. ✅ Make code production-ready on first generation

---

**Remember**: Code is written once but read many times. Write for clarity and maintainability.