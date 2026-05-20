# eventor-api-openapi-spec

[![Validate OpenAPI spec](https://github.com/orienteering-oss/eventor-api-openapi-spec/actions/workflows/validate.yml/badge.svg)](https://github.com/orienteering-oss/eventor-api-openapi-spec/actions/workflows/validate.yml)

OpenAPI spec / Swagger for the Eventor API: [openapi.yml](./openapi.yml).

You can browse the [Swagger UI](https://orienteering-oss.github.io/eventor-api-openapi-spec) for this spec, but it will not work because of CORS. You can use it to browse and create cURL commands that you can execute in your own terminal. Or you could import the OpenAPI spec into Postman and make your calls from there.

**What is Eventor?** Eventor is the event system for [orienteering](https://en.wikipedia.org/wiki/Orienteering) races in different countries, so if you want to arrange an orienteering event, you will probably register it in your local Eventor system to make other people see it and for them to register to your event (and where you can upload results after the event is done).

## Usage of the Eventor API

To use the Eventor API, you need an API key.

The different Eventor websites are:

- [Norwegian Eventor](https://eventor.orientering.no/)
- [Swedish Eventor](https://eventor.orientering.se/)
- [Australian Eventor](https://eventor.orienteering.asn.au/)
- [International Eventor](https://eventor.orienteering.sport/) (previously `eventor.orienteering.org`, which still redirects)

Add `/api/documentation` to either of the URLs to get the documentation for that particular Eventor website (the documentation is also included in the OpenAPI specification).

### Differences between Eventor instances

The Eventor instances expose nearly the same API.
This OpenAPI spec is a superset that documents every endpoint across all four instances.
The endpoints that are not available on every instance are:

| Endpoint                    | NO  | SE  | AU  | Intl |
| --------------------------- | :-: | :-: | :-: | :-:  |
| `GET /memberships`          |  –  |  –  |  ✓  |  –   |
| `GET /wrsevents`            |  –  |  –  |  –  |  ✓   |
| `GET /wrsresults/event`     |  –  |  –  |  –  |  ✓   |

All other endpoints are common to all four instances, including the IOF XML 3.0 variants (`/events/iofxml`, `/event/iofxml/{eventId}`, `/organisations/iofxml`, `/starts/event/iofxml`, `/results/event/iofxml`).
Note that some of the IOF XML endpoints are not listed on every instance's `/api/documentation` page even though they work — the OpenAPI spec is the more complete reference.

The IOF XML bodies follow the [IOF datastandard-v3 XSD](https://github.com/international-orienteering-federation/datastandard-v3) and are not duplicated in this spec; the Eventor-specific elements that appear inside `<Extensions>` (namespace `http://eventor.orientering.se/iofxmlextensions`) are documented under the `EventorExtensions` component schema.

## See also

- All data returned from the API is specified in IOF XSD v3, see this and JSON version of the same spec in [orienteering-oss/iof-orienteering-data-schemas](https://github.com/orienteering-oss/iof-orienteering-data-schemas)
- Java helper library for converting XML from Eventor to JSON objects (and back): [orienteering-oss/iof-xml](https://github.com/orienteering-oss/iof-xml)
- WIP: JavaScript helper library for converting XML from Eventor to JSON objects: [mikaello/eventor-api-json-types](https://github.com/mikaello/eventor-api-json-types)
- GraphQL version of the Eventor API: [mikaello/eventor-graphql-api](https://github.com/mikaello/eventor-graphql-api)
