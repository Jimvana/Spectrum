# Spectrum Algo — Test Source v1
# A Python Fibonacci script designed to exercise a wide range of tokens:
# keywords, operators, punctuation, digits, strings, comments, and whitespace.

def fibonacci(n):
    """Return the nth Fibonacci number (0-indexed)."""
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    elif n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        a, b = 0, 1
        for i in range(2, n + 1):
            a, b = b, a + b
        return b


def fibonacci_sequence(limit):
    """Generate all Fibonacci numbers up to (but not exceeding) limit."""
    sequence = []
    a, b = 0, 1
    while a <= limit:
        sequence.append(a)
        a, b = b, a + b
    return sequence


def is_fibonacci(num):
    """Check whether a given number is a Fibonacci number."""
    if num < 0:
        return False
    a, b = 0, 1
    while b < num:
        a, b = b, a + b
    return b == num or num == 0


class FibonacciCache:
    """Memoised Fibonacci using a class-level cache."""

    _cache = {0: 0, 1: 1}

    @classmethod
    def get(cls, n):
        if n not in cls._cache:
            cls._cache[n] = cls.get(n - 1) + cls.get(n - 2)
        return cls._cache[n]

    @classmethod
    def clear(cls):
        cls._cache = {0: 0, 1: 1}


# ---------------------------------------------------------------------------
# Main — run a quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # First 15 Fibonacci numbers
    print("First 15 Fibonacci numbers:")
    for i in range(15):
        print(f"  F({i}) = {fibonacci(i)}")

    print()

    # Sequence up to 1000
    seq = fibonacci_sequence(1000)
    print(f"Fibonacci sequence up to 1000: {seq}")

    print()

    # Membership test
    test_values = [0, 1, 4, 5, 12, 13, 100, 144, 999, 1000]
    print("Fibonacci membership test:")
    for v in test_values:
        result = is_fibonacci(v)
        print(f"  {v:>5} → {'yes' if result else 'no'}")

    print()

    # Cached version
    print("Cached Fibonacci (F(30) to F(35)):")
    for i in range(30, 36):
        print(f"  F({i}) = {FibonacciCache.get(i)}")
