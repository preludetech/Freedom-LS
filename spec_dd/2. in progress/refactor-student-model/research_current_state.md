# Research: Current Student Model State

## The Student Model

**Location**: `freedom_ls/student_management/models.py:15`

```python
class Student(SiteAwareModel):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    id_number = models.CharField(max_length=50, blank=True, default="")
    date_of_birth = models.DateField(blank=True, null=True)
    cellphone = models.CharField(max_length=20, blank=True, default="")
```

### Student-specific fields (not on User)
- `id_number` - student ID number
- `date_of_birth` - date of birth
- `cellphone` - phone number

### Methods on Student
1. `__str__()` - returns name from user or email
2. `get_course_registrations()` - gets all courses (direct + cohort-based)
3. `completed_courses()` - courses where CourseProgress has completed_time
4. `current_courses()` - non-completed courses with progress percentages

## Models with FK to Student

| Model | Field | File |
|-------|-------|------|
| `CohortMembership` | `student = FK(Student)` | `student_management/models.py:160` |
| `StudentCourseRegistration` | `student = FK(Student)` | `student_management/models.py:175` |
| `StudentCohortDeadlineOverride` | `student = FK(Student)` | `student_management/models.py:321` |

## Key Usage Points

### student_interface/utils.py
- `get_student(user)` - looks up Student from User, returns None if not found
- `get_is_registered(user, course)` - uses Student to check registration
- `get_completed_courses(user)` - delegates to student.completed_courses()
- `get_current_courses(user)` - delegates to student.current_courses()
- `get_course_index()` - gets Student for deadline lookups

### student_management/deadline_utils.py
- Nearly all functions take `student: Student` parameter
- Uses Student to look up CohortMembership, StudentCourseRegistration, StudentCohortDeadlineOverride
- The actual deadline queries use `student` FK on these related models

### educator_interface/views.py
- `StudentConfig` - list view config using Student as the model
- `StudentDataTable` - search fields reference `user__first_name`, etc.
- `StudentInstanceView` - detail view for a student
- Various panels reference student relationships

### Admin
- `StudentAdmin` - full admin for Student model
- `StudentCourseRegistrationAdmin` - references `student__user`
- `StudentCohortDeadlineOverrideAdmin` - references student
- Various inline admins

### Tests
- Tests reference Student via factories
- `StudentFactory`, `StudentCourseRegistrationFactory`, `StudentCohortDeadlineOverrideFactory`

## Important Observations

1. **Student is essentially a profile model** - it adds 3 fields (id_number, date_of_birth, cellphone) to User
2. **Student.user is a ForeignKey, not OneToOneField** - meaning a user could theoretically have multiple Student records (one per site?)
3. **The User model already has site awareness** via SiteAwareModelBase
4. **Many Student methods already use `self.user`** to query progress models (CourseProgress, TopicProgress, FormProgress all link to User, not Student)
5. **The progress models already point to User** - Student is an unnecessary intermediary for progress queries
6. **The deadline system is the most complex consumer** of Student relationships
7. **RecommendedCourse already points to User** (not Student) - showing the codebase is partially migrated already
