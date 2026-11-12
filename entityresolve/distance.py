"""Edit-distance algorithms used by name matching."""

from __future__ import annotations


def levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insertion = current[j - 1] + 1
            deletion = previous[j] + 1
            substitution = previous[j - 1] + (left_char != right_char)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]


def damerau_levenshtein(left: str, right: str) -> int:
    """Return true Damerau-Levenshtein distance; one adjacent swap costs 1."""
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    max_distance = len(left) + len(right)
    last_positions: dict[str, int] = {}
    matrix = [[0] * (len(right) + 2) for _ in range(len(left) + 2)]
    matrix[0][0] = max_distance

    for i in range(len(left) + 1):
        matrix[i + 1][0] = max_distance
        matrix[i + 1][1] = i
    for j in range(len(right) + 1):
        matrix[0][j + 1] = max_distance
        matrix[1][j + 1] = j

    for i, left_char in enumerate(left, start=1):
        last_matching_column = 0
        for j, right_char in enumerate(right, start=1):
            previous_matching_row = last_positions.get(right_char, 0)
            previous_matching_column = last_matching_column
            if left_char == right_char:
                substitution_cost = 0
                last_matching_column = j
            else:
                substitution_cost = 1

            matrix[i + 1][j + 1] = min(
                matrix[i][j + 1] + 1,
                matrix[i + 1][j] + 1,
                matrix[i][j] + substitution_cost,
                matrix[previous_matching_row][previous_matching_column]
                + (i - previous_matching_row - 1)
                + 1
                + (j - previous_matching_column - 1),
            )
        last_positions[left_char] = i

    return matrix[len(left) + 1][len(right) + 1]
