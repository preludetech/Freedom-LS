from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


def _variable_face_weights(
    family: str, static_path: str, style: str = "normal"
) -> list[dict[str, str]]:
    """One entry per weight the report asks for, all from one variable file.

    Every weight is declared even where the stylesheet uses only some of them:
    a weight with no `@font-face` rule is not an error, it is a face WeasyPrint
    synthesises by smearing the nearest one, and a synthesised bold is visibly
    coarser than a real one at print resolution.
    """
    return [
        {
            "family": family,
            "weight": weight,
            "style": style,
            "static_path": static_path,
        }
        for weight in ("400", "500", "600", "700")
    ]


# The faces the report's stylesheet is set in. Each entry names a family, a
# weight and style, and a path resolvable through the staticfiles finders.
# FLS's own brand faces are only the default: a downstream project drops its
# own files into its own static directory and overrides this setting together
# with the three stacks below, which is why print.css names no font family
# directly, exactly as it names no colour directly.
#
# DejaVu Sans is deliberately last in every stack. It is the face that carries
# the status glyphs (checkmark, cross, triangle, filled and hollow circle, em
# dash), so those keep drawing whatever brand faces replace the rest.
#
# Several weights of a family can share one file: the brand faces ship as
# upstream variable fonts, and WeasyPrint instantiates the weight axis per
# @font-face rule. They are shipped unmodified because the Source families
# reserve the name "Source" under the OFL, so an instanced copy could not keep
# its own name.
DEFAULT_REPORT_FONT_FACES = [
    *_variable_face_weights("Inter", "reports/fonts/Inter-Variable.ttf"),
    *_variable_face_weights("Source Sans 3", "reports/fonts/SourceSans3-Variable.ttf"),
    *_variable_face_weights(
        "Source Sans 3",
        "reports/fonts/SourceSans3-Italic-Variable.ttf",
        style="italic",
    ),
    *_variable_face_weights(
        "Source Code Pro", "reports/fonts/SourceCodePro-Variable.ttf"
    ),
    {
        "family": "DejaVu Sans",
        "weight": "400",
        "style": "normal",
        "static_path": "reports/fonts/DejaVuSans.ttf",
    },
    {
        "family": "DejaVu Sans",
        "weight": "700",
        "style": "normal",
        "static_path": "reports/fonts/DejaVuSans-Bold.ttf",
    },
]


class ReportsConfig(AppSettings):
    REPORTS_STORAGE_ALIAS: str
    REPORTS_AT_RISK_RULES_MODULE: str
    REPORTS_MAX_STUDENTS: int
    REPORTS_MAX_QUIZ_COLUMNS: int
    REPORTS_POWERED_BY_NAME: str | None
    REPORTS_POWERED_BY_LOGO_STATIC_PATH: str | None
    REPORTS_FONT_FACES: list[dict[str, str]]
    REPORTS_FONT_DISPLAY: str
    REPORTS_FONT_BODY: str
    REPORTS_FONT_MONO: str

    declared_settings = {
        "REPORTS_STORAGE_ALIAS": Setting(default="reports"),
        "REPORTS_AT_RISK_RULES_MODULE": Setting(
            default="freedom_ls.reports.at_risk.rules"
        ),
        # A resource guard, not a product rule: the safe ceiling depends on the
        # deployment's worker memory and render budget, which FLS cannot know.
        "REPORTS_MAX_STUDENTS": Setting(default=500),
        # A layout budget, not a product rule: 11 quiz columns (14 columns in
        # all) is the largest a summary table renders without clipping on A4
        # landscape, measured on real rendered pages. A deployment that changes
        # the page size, font or Completion column width can raise or lower it.
        "REPORTS_MAX_QUIZ_COLUMNS": Setting(default=11),
        # The report's one piece of chrome FLS holds no data for. A site's own
        # name and logo come from the Site row and HEADER_LOGO_STATIC_PATH, but
        # nothing in FLS records who runs the platform underneath it. Both
        # default to None so an unconfigured install renders no "powered by"
        # block at all, rather than an empty or invented one.
        "REPORTS_POWERED_BY_NAME": Setting(default=None),
        "REPORTS_POWERED_BY_LOGO_STATIC_PATH": Setting(default=None),
        "REPORTS_FONT_FACES": Setting(default=DEFAULT_REPORT_FONT_FACES),
        "REPORTS_FONT_DISPLAY": Setting(default='"Inter", "DejaVu Sans", sans-serif'),
        "REPORTS_FONT_BODY": Setting(
            default='"Source Sans 3", "DejaVu Sans", sans-serif'
        ),
        "REPORTS_FONT_MONO": Setting(
            default='"Source Code Pro", "DejaVu Sans", monospace'
        ),
    }


config = ReportsConfig()
