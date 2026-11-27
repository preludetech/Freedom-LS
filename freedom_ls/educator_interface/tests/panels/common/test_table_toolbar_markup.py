"""The cohort table's toolbar renders the same controls in the same order."""

from __future__ import annotations

import re
from typing import cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.test import Client, override_settings

from freedom_ls.educator_interface.tests.helpers import _interface_url
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

APPLIED_FILTER: list[str] = [
    'div [class="md:flex md:flex-wrap md:items-center md:gap-2 md:border-b md:border-border '
    'md:px-6 md:py-3 lg:min-h-16.75" x-bind:class="toolbarClass"]',
    'form [action="/educator/organisations/toolbar-org/cohorts" class="w-full px-4 pt-3 sm:px-6 '
    'md:w-auto md:min-w-40 md:max-w-72 md:flex-1 md:p-0 pb-0" '
    'hx-get="/educator/organisations/toolbar-org/cohorts" hx-swap="outerHTML" '
    'hx-sync="this:replace" hx-target="#cohorts-table" hx-trigger="submit, input changed '
    'delay:300ms from:#cohorts-q, search from:#cohorts-q" id="cohorts-search" method="get"]',
    'input [name="cohorts-sort" type="hidden" value="name"]',
    'input [name="cohorts-inactive" type="hidden" value="1"]',
    "div []",
    'label [class="sr-only" for="cohorts-q"] Search',
    'div [class="relative"]',
    'span [aria-hidden="true" class="pointer-events-none absolute inset-y-0 left-0 flex '
    'items-center pl-3 text-muted"]',
    'svg [aria-hidden="true" class="inline size-4" data-icon="search" height="24" viewbox="0 0 '
    '24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m21 21l-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607" '
    'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="1.5"]',
    'input [class="pl-9 max-md:min-h-11" hx-preserve="" id="cohorts-q" name="cohorts-q" '
    'placeholder="Search..." type="search" value=""]',
    'div [class="hidden md:contents"]',
    'details [class="group relative shrink-0"]',
    'summary [class="list-none marker:hidden [&::-webkit-details-marker]:hidden"]',
    'span [class="cursor-pointer chip chip-secondary"] Show inactive',
    'a [aria-label="Remove Show inactive filter" class="inline-flex text-current no-underline '
    'hover:text-primary" href="/educator/organisations/toolbar-org/cohorts?cohorts-sort=name" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-sort=name" hx-swap="outerHTML" '
    'hx-target="#cohorts-table"]',
    'svg [aria-hidden="true" class="inline size-3" data-icon="close" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M6 18L18 6M6 6l12 12" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'svg [aria-hidden="true" class="inline size-3 transition-transform group-open:rotate-180" '
    'data-icon="dropdown" height="24" viewbox="0 0 24 24" width="24" '
    'xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m19.5 8.25l-7.5 7.5l-7.5-7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="mt-1 min-w-40 space-y-1 surface bg-surface absolute z-10 p-2"]',
    'a [class="flex items-center gap-2 whitespace-nowrap rounded-md px-2 py-1 text-on-surface '
    'no-underline hover:bg-surface-2" '
    'href="/educator/organisations/toolbar-org/cohorts?cohorts-sort=name" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-sort=name" hx-swap="outerHTML" '
    'hx-target="#cohorts-table"]',
    'span [class="size-4 shrink-0"]',
    "text: Show inactive",
    'svg [aria-hidden="true" class="inline size-4" data-icon="check" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m4.5 12.75l6 6l9-13.5" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'a [class="btn btn-link btn-sm shrink-0 whitespace-nowrap" data-variant="link" '
    'href="/educator/organisations/toolbar-org/cohorts?cohorts-sort=name" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-sort=name" hx-swap="outerHTML" '
    'hx-target="#cohorts-table"] Clear all',
    'div [class="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3 md:hidden" '
    'data-mobile-only="true" data-storage-key="cohorts-sheet" x-data="sidePanel"]',
    'span [class="chip chip-secondary"] Show inactive',
    'a [aria-label="Remove Show inactive filter" class="inline-flex text-current no-underline '
    'hover:text-primary" href="/educator/organisations/toolbar-org/cohorts?cohorts-sort=name" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-sort=name" hx-swap="outerHTML" '
    'hx-target="#cohorts-table"]',
    'svg [aria-hidden="true" class="inline size-3" data-icon="close" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M6 18L18 6M6 6l12 12" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="flex shrink-0 items-center gap-2"]',
    'button [class="btn btn-secondary btn-sm" data-variant="secondary" type="button" '
    'x-on:click="toggle"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Filter",
    'svg [aria-hidden="true" class="inline size-5" data-icon="filter" height="24" viewbox="0 0 '
    '24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M12 3c2.755 0 5.455.232 8.083.678c.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 '
    "1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 "
    "21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 "
    '5.818V4.774c0-.54.384-1.006.917-1.096A48.3 48.3 0 0 1 12 3" fill="none" '
    'stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="relative inline-block" x-data="dropdownMenu"]',
    'button [aria-haspopup="menu" aria-label="Sort" class="group/menu btn btn-secondary btn-sm" '
    'type="button" x-bind:aria-expanded="open" x-on:click="toggle" '
    'x-on:keydown.arrow-down.prevent="openFromTrigger" '
    'x-on:keydown.arrow-up.prevent="openFromTrigger" x-ref="menuButton"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Sort",
    'svg [aria-hidden="true" class="inline size-5" data-icon="sort_neutral" height="24" '
    'viewbox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M3 4.5h14.25M3 9h9.75M3 13.5h9.75m4.5-4.5v12m0 0l-3.75-3.75M17.25 21L21 17.25" '
    'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="1.5"]',
    'div [class="dropdown-panel fixed w-56 bg-surface border border-border rounded-md shadow-lg '
    'z-[9999]" style="display: none" x-cloak="" x-on:click.away="close" '
    'x-on:keydown.arrow-down.prevent="focusNextItem" '
    'x-on:keydown.arrow-up.prevent="focusPreviousItem" x-on:keydown.end.prevent="focusLastItem" '
    'x-on:keydown.escape.window.capture="onEscape" x-on:keydown.home.prevent="focusFirstItem" '
    'x-on:scroll.window="closeOnScroll" x-ref="menuPanel" x-show="open" '
    'x-transition:enter="transition ease-out duration-100" x-transition:enter-end="transform '
    'opacity-100 scale-100" x-transition:enter-start="transform opacity-0 scale-95" '
    'x-transition:leave="transition ease-in duration-75" x-transition:leave-end="transform '
    'opacity-0 scale-95" x-transition:leave-start="transform opacity-100 scale-100"]',
    'div [aria-label="Sort by" class="py-1 space-y-1" role="menu"]',
    'a [aria-current="true" class="block w-full text-left px-4 py-2 text-sm hover:bg-surface-2 '
    "transition-colors no-underline cursor-pointer flex min-h-11 items-center justify-between "
    'text-on-surface font-semibold text-muted" '
    'href="/educator/organisations/toolbar-org/cohorts?cohorts-inactive=1&cohorts-sort=-name" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-inactive=1&cohorts-sort=-name" '
    'hx-swap="outerHTML" hx-target="#cohorts-table" role="menuitem"] Name',
    'span [aria-hidden="true"]',
    'svg [aria-hidden="true" class="inline size-5 ml-2" data-icon="sort_asc" height="24" '
    'viewbox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m4.5 15.75l7.5-7.5l7.5 7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'a [aria-current="false" class="block w-full text-left px-4 py-2 text-sm hover:bg-surface-2 '
    "transition-colors no-underline cursor-pointer flex min-h-11 items-center justify-between "
    'text-muted" '
    'href="/educator/organisations/toolbar-org/cohorts?cohorts-inactive=1&cohorts-sort=learner_count" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-inactive=1&cohorts-sort=learner_count" '
    'hx-swap="outerHTML" hx-target="#cohorts-table" role="menuitem"] Learners',
    'a [aria-current="false" class="block w-full text-left px-4 py-2 text-sm hover:bg-surface-2 '
    "transition-colors no-underline cursor-pointer flex min-h-11 items-center justify-between "
    'text-muted" '
    'href="/educator/organisations/toolbar-org/cohorts?cohorts-inactive=1&cohorts-sort=created_at" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-inactive=1&cohorts-sort=created_at" '
    'hx-swap="outerHTML" hx-target="#cohorts-table" role="menuitem"] Created',
    'dialog [aria-label="Filter" class="side-panel-dialog modal-backdrop-host bg-transparent '
    'md:hidden" data-variant="bottom-sheet" id="cohorts-sheet" x-ref="panelDialog"]',
    'div [class="side-panel-body bg-surface bottom-sheet overflow-y-auto overscroll-contain"]',
    'form [action="/educator/organisations/toolbar-org/cohorts" class="flex flex-col gap-4 p-4" '
    'hx-get="/educator/organisations/toolbar-org/cohorts" hx-swap="outerHTML" '
    'hx-target="#cohorts-table" method="get"]',
    'div [class="flex items-center gap-1"]',
    'h2 [class="flex-1 min-w-0 text-lg font-semibold"] Filter',
    'a [class="btn btn-link btn-sm min-w-11" data-variant="link" '
    'href="/educator/organisations/toolbar-org/cohorts?cohorts-sort=name" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-sort=name" hx-swap="outerHTML" '
    'hx-target="#cohorts-table"] Reset',
    'button [aria-label="Close" class="-my-2 -me-3 flex size-11 shrink-0 cursor-pointer '
    "items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-2 "
    "hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-50 "
    'disabled:hover:bg-transparent" type="button" x-bind:disabled="running" '
    'x-on:click="requestClose"]',
    'svg [aria-hidden="true" class="inline size-5" data-icon="close" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M6 18L18 6M6 6l12 12" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'fieldset [class="space-y-2 border-0 p-0"]',
    'legend [class="px-0 text-xs font-semibold uppercase tracking-wide text-muted"] Show '
    "inactive",
    'div [class="flex flex-wrap gap-2"]',
    'label [class="relative inline-flex min-h-11 cursor-pointer items-center gap-1 rounded-full '
    "border border-border px-3 py-1 text-sm has-[:checked]:border-primary "
    'has-[:checked]:bg-primary has-[:checked]:text-on-primary"]',
    'input [checked="checked" class="sr-only" name="cohorts-inactive" type="checkbox" value="1"]',
    "text: Show inactive",
    'footer [class="panel-surface shrink-0 flex items-center justify-between gap-3 border-t '
    'border-border px-6 py-4 max-sm:flex-wrap sticky bottom-0 z-10 mt-auto -mx-4 -mb-4" '
    'data-modal-footer=""]',
    'div [class="shrink-0"]',
    'button [class="btn btn-secondary" data-variant="secondary" type="button" '
    'x-bind:disabled="running" x-on:click="close"] Cancel',
    'div [class="flex min-w-0 grow flex-wrap items-center justify-end gap-3"]',
    'button [class="btn btn-primary" data-variant="primary" type="submit"] Show results',
    "style [] @media (scripting: none) { #cohorts-sheet { display: block; position: static; "
    "opacity: 1; transform: none; } }",
]

NO_FILTER_APPLIED: list[str] = [
    'div [class="md:flex md:flex-wrap md:items-center md:gap-2 md:border-b md:border-border '
    'md:px-6 md:py-3 lg:min-h-16.75" x-bind:class="toolbarClass"]',
    'form [action="/educator/organisations/toolbar-org/cohorts" class="w-full px-4 pt-3 sm:px-6 '
    'md:w-auto md:min-w-40 md:max-w-72 md:flex-1 md:p-0 pb-0" '
    'hx-get="/educator/organisations/toolbar-org/cohorts" hx-swap="outerHTML" '
    'hx-sync="this:replace" hx-target="#cohorts-table" hx-trigger="submit, input changed '
    'delay:300ms from:#cohorts-q, search from:#cohorts-q" id="cohorts-search" method="get"]',
    "div []",
    'label [class="sr-only" for="cohorts-q"] Search',
    'div [class="relative"]',
    'span [aria-hidden="true" class="pointer-events-none absolute inset-y-0 left-0 flex '
    'items-center pl-3 text-muted"]',
    'svg [aria-hidden="true" class="inline size-4" data-icon="search" height="24" viewbox="0 0 '
    '24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m21 21l-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607" '
    'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="1.5"]',
    'input [class="pl-9 max-md:min-h-11" hx-preserve="" id="cohorts-q" name="cohorts-q" '
    'placeholder="Search..." type="search" value=""]',
    'div [class="hidden md:contents"]',
    'details [class="group/add relative shrink-0"]',
    'summary [class="list-none marker:hidden [&::-webkit-details-marker]:hidden"]',
    'span [class="cursor-pointer chip chip-secondary"] Add filter',
    'svg [aria-hidden="true" class="inline size-3 transition-transform '
    'group-open/add:rotate-180" data-icon="dropdown" height="24" viewbox="0 0 24 24" width="24" '
    'xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m19.5 8.25l-7.5 7.5l-7.5-7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="surface bg-surface absolute z-10 mt-1 min-w-40 space-y-2 p-2"]',
    'details [class="group"]',
    'summary [class="list-none marker:hidden [&::-webkit-details-marker]:hidden flex '
    'cursor-pointer items-center justify-between gap-2 rounded-md px-2 py-1 hover:bg-surface-2"] '
    "Show inactive",
    'svg [aria-hidden="true" class="inline size-3 text-muted transition-transform '
    'group-open:rotate-180" data-icon="dropdown" height="24" viewbox="0 0 24 24" width="24" '
    'xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m19.5 8.25l-7.5 7.5l-7.5-7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="mt-1 min-w-40 space-y-1 ps-2"]',
    'a [class="flex items-center gap-2 whitespace-nowrap rounded-md px-2 py-1 text-on-surface '
    'no-underline hover:bg-surface-2" '
    'href="/educator/organisations/toolbar-org/cohorts?cohorts-inactive=1" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-inactive=1" hx-swap="outerHTML" '
    'hx-target="#cohorts-table"]',
    'span [class="size-4 shrink-0"]',
    "text: Show inactive",
    'div [class="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3 md:hidden" '
    'data-mobile-only="true" data-storage-key="cohorts-sheet" x-data="sidePanel"]',
    'div [class="flex shrink-0 items-center gap-2"]',
    'button [class="btn btn-secondary btn-sm" data-variant="secondary" type="button" '
    'x-on:click="toggle"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Filter",
    'svg [aria-hidden="true" class="inline size-5" data-icon="filter" height="24" viewbox="0 0 '
    '24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M12 3c2.755 0 5.455.232 8.083.678c.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 '
    "1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 "
    "21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 "
    '5.818V4.774c0-.54.384-1.006.917-1.096A48.3 48.3 0 0 1 12 3" fill="none" '
    'stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'div [class="relative inline-block" x-data="dropdownMenu"]',
    'button [aria-haspopup="menu" aria-label="Sort" class="group/menu btn btn-secondary btn-sm" '
    'type="button" x-bind:aria-expanded="open" x-on:click="toggle" '
    'x-on:keydown.arrow-down.prevent="openFromTrigger" '
    'x-on:keydown.arrow-up.prevent="openFromTrigger" x-ref="menuButton"]',
    'span [aria-hidden="true" class="inline-flex"]',
    "text: Sort",
    'svg [aria-hidden="true" class="inline size-5" data-icon="sort_neutral" height="24" '
    'viewbox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M3 4.5h14.25M3 9h9.75M3 13.5h9.75m4.5-4.5v12m0 0l-3.75-3.75M17.25 21L21 17.25" '
    'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="1.5"]',
    'div [class="dropdown-panel fixed w-56 bg-surface border border-border rounded-md shadow-lg '
    'z-[9999]" style="display: none" x-cloak="" x-on:click.away="close" '
    'x-on:keydown.arrow-down.prevent="focusNextItem" '
    'x-on:keydown.arrow-up.prevent="focusPreviousItem" x-on:keydown.end.prevent="focusLastItem" '
    'x-on:keydown.escape.window.capture="onEscape" x-on:keydown.home.prevent="focusFirstItem" '
    'x-on:scroll.window="closeOnScroll" x-ref="menuPanel" x-show="open" '
    'x-transition:enter="transition ease-out duration-100" x-transition:enter-end="transform '
    'opacity-100 scale-100" x-transition:enter-start="transform opacity-0 scale-95" '
    'x-transition:leave="transition ease-in duration-75" x-transition:leave-end="transform '
    'opacity-0 scale-95" x-transition:leave-start="transform opacity-100 scale-100"]',
    'div [aria-label="Sort by" class="py-1 space-y-1" role="menu"]',
    'a [aria-current="true" class="block w-full text-left px-4 py-2 text-sm hover:bg-surface-2 '
    "transition-colors no-underline cursor-pointer flex min-h-11 items-center justify-between "
    'text-on-surface font-semibold text-muted" '
    'href="/educator/organisations/toolbar-org/cohorts?cohorts-sort=-name" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-sort=-name" hx-swap="outerHTML" '
    'hx-target="#cohorts-table" role="menuitem"] Name',
    'span [aria-hidden="true"]',
    'svg [aria-hidden="true" class="inline size-5 ml-2" data-icon="sort_asc" height="24" '
    'viewbox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="m4.5 15.75l7.5-7.5l7.5 7.5" fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"]',
    'a [aria-current="false" class="block w-full text-left px-4 py-2 text-sm hover:bg-surface-2 '
    "transition-colors no-underline cursor-pointer flex min-h-11 items-center justify-between "
    'text-muted" href="/educator/organisations/toolbar-org/cohorts?cohorts-sort=learner_count" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-sort=learner_count" '
    'hx-swap="outerHTML" hx-target="#cohorts-table" role="menuitem"] Learners',
    'a [aria-current="false" class="block w-full text-left px-4 py-2 text-sm hover:bg-surface-2 '
    "transition-colors no-underline cursor-pointer flex min-h-11 items-center justify-between "
    'text-muted" href="/educator/organisations/toolbar-org/cohorts?cohorts-sort=created_at" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?cohorts-sort=created_at" '
    'hx-swap="outerHTML" hx-target="#cohorts-table" role="menuitem"] Created',
    'dialog [aria-label="Filter" class="side-panel-dialog modal-backdrop-host bg-transparent '
    'md:hidden" data-variant="bottom-sheet" id="cohorts-sheet" x-ref="panelDialog"]',
    'div [class="side-panel-body bg-surface bottom-sheet overflow-y-auto overscroll-contain"]',
    'form [action="/educator/organisations/toolbar-org/cohorts" class="flex flex-col gap-4 p-4" '
    'hx-get="/educator/organisations/toolbar-org/cohorts" hx-swap="outerHTML" '
    'hx-target="#cohorts-table" method="get"]',
    'div [class="flex items-center gap-1"]',
    'h2 [class="flex-1 min-w-0 text-lg font-semibold"] Filter',
    'a [class="btn btn-link btn-sm min-w-11" data-variant="link" '
    'href="/educator/organisations/toolbar-org/cohorts?" '
    'hx-get="/educator/organisations/toolbar-org/cohorts?" hx-swap="outerHTML" '
    'hx-target="#cohorts-table"] Reset',
    'button [aria-label="Close" class="-my-2 -me-3 flex size-11 shrink-0 cursor-pointer '
    "items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-2 "
    "hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-50 "
    'disabled:hover:bg-transparent" type="button" x-bind:disabled="running" '
    'x-on:click="requestClose"]',
    'svg [aria-hidden="true" class="inline size-5" data-icon="close" height="24" viewbox="0 0 24 '
    '24" width="24" xmlns="http://www.w3.org/2000/svg"]',
    'path [d="M6 18L18 6M6 6l12 12" fill="none" stroke="currentColor" stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="1.5"]',
    'fieldset [class="space-y-2 border-0 p-0"]',
    'legend [class="px-0 text-xs font-semibold uppercase tracking-wide text-muted"] Show '
    "inactive",
    'div [class="flex flex-wrap gap-2"]',
    'label [class="relative inline-flex min-h-11 cursor-pointer items-center gap-1 rounded-full '
    "border border-border px-3 py-1 text-sm has-[:checked]:border-primary "
    'has-[:checked]:bg-primary has-[:checked]:text-on-primary"]',
    'input [class="sr-only" name="cohorts-inactive" type="checkbox" value="1"]',
    "text: Show inactive",
    'footer [class="panel-surface shrink-0 flex items-center justify-between gap-3 border-t '
    'border-border px-6 py-4 max-sm:flex-wrap sticky bottom-0 z-10 mt-auto -mx-4 -mb-4" '
    'data-modal-footer=""]',
    'div [class="shrink-0"]',
    'button [class="btn btn-secondary" data-variant="secondary" type="button" '
    'x-bind:disabled="running" x-on:click="close"] Cancel',
    'div [class="flex min-w-0 grow flex-wrap items-center justify-end gap-3"]',
    'button [class="btn btn-primary" data-variant="primary" type="submit"] Show results',
    "style [] @media (scripting: none) { #cohorts-sheet { display: block; position: static; "
    "opacity: 1; transform: none; } }",
]


def _normalised_toolbar(html: str) -> list[str]:
    """One entry per element of the toolbar, and per run of text after one: tag,
    sorted attributes and the element's own text, with the organisation slug
    made constant."""
    document = lxml.html.fromstring(html)
    (search_form,) = document.cssselect("form#cohorts-search")
    toolbar = search_form.getparent()
    entries: list[str] = []
    for element in toolbar.iter():
        if not isinstance(element.tag, str):
            continue
        attributes = " ".join(
            f'{name}="{" ".join(value.split())}"'
            for name, value in sorted(element.attrib.items())
        )
        text = re.sub(r"\s+", " ", element.text or "").strip()
        entries.append(f"{element.tag} [{attributes}] {text}".strip())
        tail = re.sub(r"\s+", " ", element.tail or "").strip()
        if tail and element is not toolbar:
            entries.append(f"text: {tail}")
    return entries


@pytest.fixture
def toolbar_organisation(mock_site_context: Site) -> Organisation:
    organisation = OrganisationFactory(slug="toolbar-org")
    CohortFactory(organisation=organisation, name="Morning group")
    return cast(Organisation, organisation)


def _toolbar_for(
    staff_client: Client, organisation: Organisation, query: str
) -> list[str]:
    # The expected markup holds heroicons' SVGs, so pin the set: a concrete project
    # running this suite may configure another one.
    with override_settings(SEMANTIC_ICONS_SET="heroicons"):
        html = staff_client.get(
            _interface_url(organisation.slug, "cohorts") + query
        ).content.decode()
    return _normalised_toolbar(html)


@pytest.mark.django_db
def test_the_toolbar_with_a_filter_applied_renders_the_same_controls_in_order(
    staff_client: Client, toolbar_organisation: Organisation
) -> None:
    assert (
        _toolbar_for(
            staff_client, toolbar_organisation, "?cohorts-inactive=1&cohorts-sort=name"
        )
        == APPLIED_FILTER
    )


@pytest.mark.django_db
def test_the_toolbar_with_no_filter_applied_renders_the_same_controls_in_order(
    staff_client: Client, toolbar_organisation: Organisation
) -> None:
    assert _toolbar_for(staff_client, toolbar_organisation, "") == NO_FILTER_APPLIED


@pytest.mark.django_db
@override_settings(SEMANTIC_ICONS_SET="phosphor")
def test_the_toolbar_comparison_holds_when_the_project_uses_another_icon_set(
    staff_client: Client, toolbar_organisation: Organisation
) -> None:
    assert _toolbar_for(staff_client, toolbar_organisation, "") == NO_FILTER_APPLIED
