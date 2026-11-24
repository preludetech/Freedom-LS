# ruff: noqa: T201, S101 -- a manage.py shell script run by hand; output and checks are for the QA operator

import re
from pathlib import Path

import yaml

from django.contrib.sites.models import Site

from freedom_ls.content_engine.models import Course, CourseCategory
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormQuestion,
    QuestionOption,
)

ROOT = Path("SCRATCH/demo_content_remap")  # set to your scratch copy before running
dd = Site.objects.get(name="DemoDev")
mapping = {}


def add(file_uuid, row):
    assert row is not None, file_uuid
    mapping[file_uuid] = str(row.pk)


def docs(p):
    return [d for d in yaml.safe_load_all(p.read_text()) if d]


pools = ROOT / "functionality_demo_question_pools"
add(
    docs(pools / "course.md")[0]["uuid"],
    Course._base_manager.get(site=dd, slug="functionality-demo-question-pools"),
)
form = Form._base_manager.get(site=dd, slug="question-pool-quiz")
add(docs(pools / "01. quiz" / "form.md")[0]["uuid"], form)
for f in sorted((pools / "01. quiz").glob("*.yaml")):
    ds = docs(f)
    page = FormPage._base_manager.get(form=form, title=ds[0]["title"])
    add(ds[0]["uuid"], page)
    for d in ds[1:]:
        if "question" in d:
            q = FormQuestion._base_manager.get(form_page=page, question=d["question"])
            add(d["uuid"], q)
            for o in d.get("options", []):
                add(
                    o["uuid"],
                    QuestionOption._base_manager.get(question=q, text=o["text"]),
                )
        else:
            fc = [
                c
                for c in FormContent._base_manager.filter(form_page=page)
                if c.content.strip() == d["content"].strip()
            ]
            assert len(fc) == 1, d["content"]
            add(d["uuid"], fc[0])
for d in docs(ROOT / "course_categories.yaml")[0]["categories"]:
    add(d["uuid"], CourseCategory._base_manager.get(site=dd, slug=d["slug"]))
print("mapped", len(mapping))
targets = [
    ROOT / "course_categories.yaml",
    *pools.rglob("*.md"),
    *pools.rglob("*.yaml"),
]
for p in targets:
    t = p.read_text()
    for a, b in mapping.items():
        t = t.replace(a, b)
    p.write_text(t)
left = [
    u
    for p in targets
    for u in re.findall(r"uuid: (\S+)", p.read_text())
    if u in mapping
]
print("unmapped leftovers", left)
