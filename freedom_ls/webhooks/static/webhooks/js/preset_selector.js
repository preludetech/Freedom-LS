(function () {
  "use strict";

  /**
   * Preset selector for WebhookEndpoint admin form.
   *
   * Reads preset data from a JSON script block (id="webhook-preset-data")
   * and populates form fields when the preset dropdown changes.
   */

  function getPresetData() {
    var el = document.getElementById("webhook-preset-data");
    if (!el) return {};
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return {};
    }
  }

  function getFormField(name) {
    return document.getElementById("id_" + name);
  }

  function setAceEditorValue(fieldName, value) {
    var textarea = getFormField(fieldName);
    if (!textarea) return;

    // django-ace wraps textareas in a div with an ace editor
    var editorEl = textarea.parentElement
      ? textarea.parentElement.querySelector(".ace_editor")
      : null;
    if (editorEl) {
      var editor = ace.edit(editorEl);
      editor.setValue(value, -1); // -1 moves cursor to start
    } else {
      // Fallback: set textarea directly
      textarea.value = value;
    }
  }

  function getFieldValue(name) {
    var field = getFormField(name);
    if (!field) return "";

    // Check for ace editor
    var editorEl = field.parentElement
      ? field.parentElement.querySelector(".ace_editor")
      : null;
    if (editorEl) {
      var editor = ace.edit(editorEl);
      return editor.getValue();
    }
    return field.value;
  }

  function hasUserEdits() {
    var fieldsToCheck = [
      "url",
      "http_method",
      "content_type",
      "headers_template",
      "body_template",
    ];
    for (var i = 0; i < fieldsToCheck.length; i++) {
      var val = getFieldValue(fieldsToCheck[i]);
      if (val && val.trim() !== "") return true;
    }
    return false;
  }

  function applyPreset(preset) {
    var urlField = getFormField("url");
    if (urlField && preset.default_url) {
      urlField.value = preset.default_url;
    }

    var methodField = getFormField("http_method");
    if (methodField && preset.http_method) {
      methodField.value = preset.http_method;
    }

    var contentTypeField = getFormField("content_type");
    if (contentTypeField && preset.content_type) {
      contentTypeField.value = preset.content_type;
    }

    if (preset.headers_template !== undefined) {
      setAceEditorValue("headers_template", preset.headers_template);
    }

    if (preset.body_template !== undefined) {
      setAceEditorValue("body_template", preset.body_template);
    }
  }

  function init() {
    var presetSelect = getFormField("preset_slug");
    if (!presetSelect) return;

    var presets = getPresetData();

    presetSelect.addEventListener("change", function () {
      var slug = presetSelect.value;
      if (!slug) return;

      var preset = presets[slug];
      if (!preset) return;

      if (hasUserEdits()) {
        if (
          !confirm(
            "Selecting a preset will overwrite the current field values. Continue?"
          )
        ) {
          return;
        }
      }

      applyPreset(preset);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
