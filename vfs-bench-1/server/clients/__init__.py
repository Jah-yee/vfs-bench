# The client side of every fake both arms reach: `gws` and `notion` speak
# HTTP to mirage's own mock servers, `cloud_logging` to the fixture API,
# and `snowflake` is SQL on the fixture Postgres wearing a vendor's API.
#
# They live together because they are called from both surfaces. The mirage
# arm's CLIs import them by name; upstream's MCP servers and evaluators
# reach the same modules through `redirect/`, which shadows the name each
# one is normally imported under. Nothing here knows it is a substitute --
# the deception is entirely `redirect/`'s.
