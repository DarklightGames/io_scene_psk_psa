from typing import Tuple

class SemanticVersion(object):
    def __init__(self, version: Tuple[int, int, int]):
        self.major, self.minor, self.patch = version

    def __iter__(self):
        yield self.major
        yield self.minor
        yield self.patch

    @staticmethod
    def compare(lhs: 'SemanticVersion', rhs: 'SemanticVersion') -> int:
        """
        Compares two semantic versions.

        Returns:
            -1 if lhs < rhs
             0 if lhs == rhs
             1 if lhs > rhs
        """
        for l, r in zip(lhs, rhs):
            if l < r:
                return -1
            if l > r:
                return 1
        return 0

    def __str__(self):
        return f'{self.major}.{self.minor}.{self.patch}'

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return self.compare(self, other) == 0

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        return self.compare(self, other) == -1

    def __le__(self, other):
        return self.compare(self, other) <= 0

    def __gt__(self, other):
        return self.compare(self, other) == 1

    def __ge__(self, other):
        return self.compare(self, other) >= 0

    def __hash__(self):
        return hash((self.major, self.minor, self.patch))
