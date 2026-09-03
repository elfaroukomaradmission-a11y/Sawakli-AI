from typing import Any

type JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]

type JSONDict = dict[str, JSONValue]

type Payload = dict[str, Any]
