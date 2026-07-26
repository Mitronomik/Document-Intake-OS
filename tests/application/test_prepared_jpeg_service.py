from document_intake.application.services.prepared_jpeg import prepare_geometry_recipe_as_jpeg


def test_service_public_signature_is_recipe_specific() -> None:
    import inspect

    assert tuple(inspect.signature(prepare_geometry_recipe_as_jpeg).parameters) == (
        "command",
        "decoder",
        "renderer",
        "encoder",
        "storage",
        "unit_of_work_factory",
    )
