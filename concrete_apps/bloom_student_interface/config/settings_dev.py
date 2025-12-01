from config.settings_dev import *

INSTALLED_APPS = ["bloom_student_interface"] + INSTALLED_APPS


ROOT_URLCONF = "bloom_student_interface.config.urls"


UNFOLD = {
    "SITE_TITLE": "Bloom",
    "SITE_HEADER": "Bloom",
    "SHOW_VIEW_ON_SITE": False,
    "COLORS": {
        "base": {
            "50": "oklch(98.5% .002 247.839)",
            "100": "oklch(96.7% .003 264.542)",
            "200": "oklch(92.8% .006 264.531)",
            "300": "oklch(87.2% .01 258.338)",
            "400": "oklch(70.7% .022 261.325)",
            "500": "oklch(55.1% .027 264.364)",
            "600": "oklch(44.6% .03 256.802)",
            "700": "oklch(37.3% .034 259.733)",
            "800": "oklch(27.8% .033 256.848)",
            "900": "oklch(21% .034 264.665)",
            "950": "oklch(13% .028 261.692)",
        },
        "primary": {
            "50": "oklch(97.5% .015 145)",
            "100": "oklch(94.5% .035 145)",
            "200": "oklch(89.5% .070 145)",
            "300": "oklch(82.0% .130 145)",
            "400": "oklch(70.5% .180 145)",
            "500": "oklch(62.0% .210 145)",
            "600": "oklch(54.0% .220 145)",
            "700": "oklch(46.5% .200 145)",
            "800": "oklch(40.0% .165 145)",
            "900": "oklch(34.0% .130 145)",
            "950": "oklch(26.0% .100 145)",
        },
        "font": {
            "subtle-light": "var(--color-base-500)",  # text-base-500
            "subtle-dark": "var(--color-base-400)",  # text-base-400
            "default-light": "var(--color-base-600)",  # text-base-600
            "default-dark": "var(--color-base-300)",  # text-base-300
            "important-light": "var(--color-base-900)",  # text-base-900
            "important-dark": "var(--color-base-100)",  # text-base-100
        },
    },
}
