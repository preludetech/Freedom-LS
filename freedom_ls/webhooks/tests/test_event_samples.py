from freedom_ls.base.webhook_event_types import (
    FLS_WEBHOOK_EVENT_TYPES,
    WEBHOOK_EVENT_TYPE_SAMPLES,
)


class TestWebhookEventTypeSamples:
    def test_every_event_type_has_a_sample(self) -> None:
        """Every event type in FLS_WEBHOOK_EVENT_TYPES must have a corresponding sample."""
        event_type_keys = {et[0] for et in FLS_WEBHOOK_EVENT_TYPES}
        sample_keys = set(WEBHOOK_EVENT_TYPE_SAMPLES.keys())
        missing = event_type_keys - sample_keys
        assert not missing, f"Event types missing samples: {missing}"

    def test_no_extra_samples_without_event_types(self) -> None:
        """Samples should not exist for event types that are not registered."""
        event_type_keys = {et[0] for et in FLS_WEBHOOK_EVENT_TYPES}
        sample_keys = set(WEBHOOK_EVENT_TYPE_SAMPLES.keys())
        extra = sample_keys - event_type_keys
        assert not extra, f"Samples without matching event types: {extra}"

    def test_samples_are_non_empty_dicts(self) -> None:
        """Each sample must be a non-empty dict."""
        for event_type, sample in WEBHOOK_EVENT_TYPE_SAMPLES.items():
            assert isinstance(sample, dict), f"Sample for {event_type} is not a dict"
            assert len(sample) > 0, f"Sample for {event_type} is empty"
