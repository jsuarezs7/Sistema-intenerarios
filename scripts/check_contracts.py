"""Check event examples and repository deployment references without external services."""

from pathlib import Path

import jsonschema
import yaml
from itinerary_shared.events import ItineraryCreatedEvent

root = Path(__file__).resolve().parents[1]
spec = yaml.safe_load((root / "docs/asyncapi.yaml").read_text(encoding="utf-8"))
schema = spec["components"]["schemas"]["ItineraryCreatedEvent"]
jsonschema.Draft7Validator.check_schema(schema)
assert set(schema["properties"]) == set(ItineraryCreatedEvent.model_fields)
for example in spec["components"]["messages"]["ItineraryCreatedEvent"]["examples"]:
    jsonschema.validate(example["payload"], schema, format_checker=jsonschema.FormatChecker())
    ItineraryCreatedEvent.model_validate(example["payload"])
blueprint = yaml.safe_load((root / "render.yaml").read_text(encoding="utf-8"))
services = {service["name"]: service for service in blueprint["services"]}
databases = {database["name"] for database in blueprint["databases"]}
for service in services.values():
    if service.get("runtime") == "docker":
        assert (root / service["dockerfilePath"]).is_file()
    for variable in service.get("envVars", []):
        if "fromService" in variable:
            reference = variable["fromService"]
            assert reference["name"] in services
            assert reference["type"] == services[reference["name"]]["type"]
        if "fromDatabase" in variable:
            assert variable["fromDatabase"]["name"] in databases
assert {service["name"] for service in services.values() if service["type"] == "web"} == {
    "api-gateway"
}
print("PASS: event schema/examples, Dockerfile paths, Render references and single public gateway")
