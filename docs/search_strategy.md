# Search Logic Overview

The project originally referenced a `share_structure.txt` example which
outlined common folder names like `Stock`, `WoodWay/WW`, and
`Шпон в Україні/Baykal`. The file is not present in the repository, but the
following strategy was derived from the description in the prompt.

- **Board images by default** — search results exclude any path containing the
  word `Stock` unless the query explicitly mentions stock words (e.g. `stock`,
  `сток`, `склад`).
- **Brand handling** — queries containing brand identifiers such as `WoodWay`,
  `WW`, `Байкал/Baykal` or `Шпон` return photos from those folders first and also
  allow logo images.
- **Transliteration support** — the index stores both the original token and its
  ASCII transliteration using `Unidecode`. This allows English queries to match
  Ukrainian or russian names.
- **Logo filtering** — non-brand queries ignore files whose path includes
  `logo`.

This document summarises how the search utilities filter and prioritise results.
