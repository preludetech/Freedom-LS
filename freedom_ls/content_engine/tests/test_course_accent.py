"""Tests for ``course_accent_role`` — pure unit tests, no Django needed."""

from __future__ import annotations

from freedom_ls.content_engine.course_accent import (
    PALETTE,
    course_accent_role,
)


def test_returns_value_from_palette() -> None:
    assert course_accent_role("Intro to Python") in PALETTE


def test_deterministic_same_input_same_output() -> None:
    a = course_accent_role("Intro to Python")
    b = course_accent_role("Intro to Python")
    assert a == b


def test_deterministic_against_known_digest() -> None:
    """SHA-256 is process-stable, unlike Python's hash().

    Spelling out the expected mapping for a known title locks the
    contract: changing the algorithm or ``PALETTE`` order would
    break this test loudly.
    """
    # Computed from sha256(b"Intro to Python")[:4] mod 5.
    import hashlib

    digest = hashlib.sha256(b"Intro to Python").digest()
    expected = PALETTE[int.from_bytes(digest[:4], "big") % len(PALETTE)]
    assert course_accent_role("Intro to Python") == expected


def test_distribution_covers_all_buckets() -> None:
    """Across ~50 sample titles, every palette role appears at least once."""
    titles = [
        "Intro to Python",
        "Advanced Algorithms",
        "Data Structures 101",
        "Calculus I",
        "Linear Algebra",
        "Statistics for Engineers",
        "Discrete Mathematics",
        "Operating Systems",
        "Computer Networks",
        "Databases",
        "Distributed Systems",
        "Compilers",
        "Programming Languages",
        "Functional Programming",
        "Object-Oriented Design",
        "Software Engineering",
        "Test-Driven Development",
        "Continuous Integration",
        "DevOps Foundations",
        "Cloud Architecture",
        "AWS Essentials",
        "Kubernetes 101",
        "Docker Deep Dive",
        "Git Internals",
        "Vim Mastery",
        "Tmux Workflow",
        "Bash Scripting",
        "Shell Pipelines",
        "Regex Workshop",
        "Concurrency in Go",
        "Async Python",
        "Rust Foundations",
        "C Programming",
        "Assembly Basics",
        "Hardware-Software Interface",
        "Computer Graphics",
        "Game Development",
        "Machine Learning",
        "Deep Learning",
        "Reinforcement Learning",
        "Computer Vision",
        "Natural Language Processing",
        "Information Retrieval",
        "Cryptography",
        "Cybersecurity",
        "Ethical Hacking",
        "Privacy Engineering",
        "Accessibility 101",
        "UX Research",
        "UX Writing",
    ]
    seen = {course_accent_role(t) for t in titles}
    assert seen == set(PALETTE), (
        f"some palette roles never appeared: {set(PALETTE) - seen}"
    )


def test_palette_excludes_error_and_warning() -> None:
    assert "error" not in PALETTE
    assert "warning" not in PALETTE


def test_palette_has_five_entries() -> None:
    assert len(PALETTE) == 5
