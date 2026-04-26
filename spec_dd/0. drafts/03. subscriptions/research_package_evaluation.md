# Package Evaluation: django-rules and django-fsm-2

Evaluated for the FLS subscription and content access system. Date: 2026-04-06.

---

## 1. django-rules (predicate-based permissions)

**Package:** [rules on PyPI](https://pypi.org/project/rules/) | [GitHub](https://github.com/dfunckt/django-rules)

### Maintenance status

| Metric | Value |
|---|---|
| Latest version | 3.5 (September 2, 2024) |
| Last commit | September 2024 |
| Open issues | 29 |
| Open PRs | 12 |
| Python classifiers | 3.8 -- 3.12 only |
| Django requirement | 3.2+ |
| License | MIT |

**No release or commit activity for 18+ months.** Python 3.13 and 3.14 are not listed in classifiers. Django 6.x is not explicitly tested. The package may work on newer versions (it has no compiled extensions and minimal Django API surface), but there is no CI confirmation.

### How it works

django-rules provides composable, database-free predicates for object-level permissions:

```python
import rules

@rules.predicate
def has_active_subscription(user, content):
    return user.subscriptions.filter(site=content.site, status="active").exists()

@rules.predicate
def is_free_content(user, content):
    return content.access_level == "FREE"

# Compose with boolean operators
rules.add_perm("content.view", has_active_subscription | is_free_content)

# Test in views
rules.has_perm("content.view", user, content_obj)
```

It integrates with Django's `PermissionRequiredMixin`, admin, and templates. Predicates support `&`, `|`, `^`, `~` operators with short-circuit evaluation.

### Pros

- Clean, declarative API for combining access predicates
- No database tables -- pure Python logic
- Integrates with Django's existing permission framework
- Well-documented and well-tested (2000+ GitHub stars)

### Cons

- **Stale maintenance**: No activity since September 2024. No Python 3.13+ or Django 6.x in CI
- **Risk of abandonment**: 12 unmerged PRs is a warning sign
- **Small core**: The predicate engine is ~265 lines of code. The full package is small enough that the value over custom code is marginal
- **Not needed for our access pattern**: Our access checks boil down to a two-layer boolean (subscription active OR content is free). This does not require a predicate composition framework

### Assessment for FLS

The FLS content access check is straightforward:

```python
def can_access_content(user, content, site) -> bool:
    access_level = content.get_effective_access_level(site)
    if access_level == AccessLevel.FREE:
        return True
    return has_active_subscription(user, site)
```

This is a simple function. django-rules would let us write it as `has_active_subscription | is_free_content` instead, but that syntactic convenience does not justify adding a dependency with uncertain maintenance. If access rules become significantly more complex in future (dozens of combinable predicates), the pattern could be adopted without the package.

**Recommendation: Do not adopt.** Write a small custom access check module. The predicate composition pattern is easy to replicate if needed later. The maintenance risk is not worth the marginal API benefit.

---

## 2. django-fsm-2 (finite state machine)

**Package:** [django-fsm-2 on PyPI](https://pypi.org/project/django-fsm-2/) | [GitHub](https://github.com/django-commons/django-fsm-2)

### Maintenance status

| Metric | Value |
|---|---|
| Latest version | 4.2.4 (March 16, 2026) |
| Maintained by | [django-commons](https://github.com/django-commons) |
| Python support | 3.10, 3.11, 3.12, 3.13, 3.14 |
| Django support | 4.2, 5.0, 5.1, 5.2, 6.0 |
| Status | Production/Stable |
| License | MIT |

**Actively maintained.** Regular releases (7 releases in the last 18 months). Explicitly supports Django 6.0 and Python 3.13+. Backed by django-commons, a community organisation that maintains orphaned Django packages.

### How it works

django-fsm-2 adds declarative state transitions to Django model fields:

```python
import django_fsm as fsm

class Subscription(fsm.FSMModelMixin, models.Model):
    state = fsm.FSMField(default="trialing")

    @fsm.transition(field=state, source="trialing", target="active")
    def activate(self):
        """Transition from trial to active subscription."""
        pass

    @fsm.transition(field=state, source="active", target="expired")
    def expire(self):
        pass

    @fsm.transition(
        field=state,
        source=["trialing", "active"],
        target="cancelled",
        conditions=[lambda self: not self.has_pending_payment],
    )
    def cancel(self):
        pass
```

Key features:
- **`protected=True`**: Prevents direct field assignment, forcing all changes through transition methods
- **`conditions`**: List of callables that must return truthy for the transition to proceed
- **`permission`**: Django permission string or callable for authorization checks
- **`on_error`**: Target state when a transition raises an exception
- **`source='*'`**: Wildcard for transitions allowed from any state
- **Dynamic targets**: `fsm.RETURN_VALUE()` lets the method determine the target state at runtime
- State changes happen in memory; `save()` must be called explicitly

### Pros

- **Actively maintained** with Django 6.0 and Python 3.13+ support confirmed
- **Declarative**: Transition rules are defined once, adjacent to the model, making the state machine self-documenting
- **Protected fields**: Prevents accidental state corruption from direct assignment
- **Conditions and permissions**: Built-in support for transition guards
- **Drop-in replacement**: Uses standard Django model fields -- no schema lock-in
- **Backed by django-commons**: Reduces single-maintainer risk
- **Well-proven**: Fork of a widely-used package (django-fsm had 2000+ stars)

### Cons

- **Additional dependency**: Adds a package for something that could be done with methods + a CharField
- **In-memory transitions**: State changes are not atomic with `save()` by default (need `django_fsm.ConcurrentTransitionMixin` or manual handling)
- **Learning curve**: Developers need to understand the decorator-based API
- **Overhead for simple cases**: If the subscription state machine stays small (6 states, ~10 transitions), a custom implementation is not much code

### Assessment for FLS

The FLS subscription system has a well-defined state machine with 6 states and multiple transitions with validation rules. This is exactly the use case django-fsm-2 was built for:

1. **Enforced transitions**: `protected=True` prevents setting `subscription.state = "active"` directly, catching bugs early
2. **Self-documenting**: The transition decorators serve as living documentation of allowed state changes
3. **Conditions**: Transition guards (e.g., "can only cancel if no pending payment") are declared inline
4. **Testability**: Each transition is a method that can be unit tested independently
5. **Future-proof**: Adding states or transitions is adding a decorated method, not refactoring conditional logic

A custom implementation would need to replicate: transition validation, protection against direct assignment, condition checking, and permission integration. That is ~200-300 lines of framework code that django-fsm-2 provides, tested and maintained.

**Recommendation: Adopt.** django-fsm-2 is actively maintained, supports our stack, and provides meaningful value for subscription state management. The protected field and declarative transition patterns will prevent bugs as the state machine grows. The django-commons backing mitigates maintenance risk.

---

## Summary

| Package | Recommendation | Reason |
|---|---|---|
| django-rules | **Do not adopt** | Stale maintenance (18+ months inactive). No Django 6.x / Python 3.13+ CI. The access check is too simple to justify a dependency -- a custom function is clearer and has zero risk. |
| django-fsm-2 | **Adopt** | Actively maintained, supports Django 6.0 + Python 3.13, backed by django-commons. Provides real value: protected state fields, declarative transitions, condition guards. Worth the dependency for a subscription state machine. |

### Custom implementation notes

For **content access checks** (replacing django-rules), implement a simple module:

```python
# freedom_ls/subscriptions/access.py

def can_access_content(user, content, site) -> bool:
    effective_level = content.get_effective_access_level(site)
    if effective_level == AccessLevel.FREE:
        return True
    return has_active_subscription(user, site)
```

This can be wrapped in a decorator/mixin for views. If predicate composition becomes needed later, the pattern is simple to add without a package.

For **subscription state management** (using django-fsm-2), install and use directly:

```
uv add django-fsm-2
```

---

## Sources

- [rules on PyPI](https://pypi.org/project/rules/)
- [django-rules on GitHub](https://github.com/dfunckt/django-rules)
- [django-fsm-2 on PyPI](https://pypi.org/project/django-fsm-2/)
- [django-fsm-2 on GitHub](https://github.com/django-commons/django-fsm-2)
- [django-fsm-2 releases](https://github.com/django-commons/django-fsm-2/releases)
- [django-commons organisation](https://github.com/django-commons)
