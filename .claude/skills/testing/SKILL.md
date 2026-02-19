---
name: unit-tests
description: Write pytest tests. Use when implementing features, fixing bugs, or when the user mentions testing, TDD, or pytest
allowed-tools: Read, Grep, Glob
---

# Testing

This Skill helps implement features and fix bugs using Test-Driven Development, following the Red-Green-Refactor cycle.

## When to Use This Skill

Use this Skill when:
- **Implementing new features** - Write tests first, then implement
- **Fixing bugs** - Write failing test, then fix
- **User mentions "TDD", "test", "pytest"**
- **Adding functionality** - Use TDD to design it
- **Refactoring code** - Ensure tests pass throughout

## Key Rules

- Test files: `freedom_ls/<app_name>/tests/test_<module>.py`
- Use `@pytest.mark.django_db` for database tests
- Use `mock_site_context` fixture for site-aware models — never manually set site
- Use `reverse()` for URLs, never hardcode
- No conditionals in tests — one assertion focus per test
- TDD cycle: RED (failing test) -> GREEN (minimal code) -> REFACTOR -> REPEAT

Refer to @.claude/docs/testing.md for full patterns and examples.