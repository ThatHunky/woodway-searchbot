# Search Logic Overview

The sample `share_structure.txt` shows a network share with several language and brand conventions:

* Folders like `Stock` store background or web images not related to specific boards.
* Product photos live under directories such as `Дошка`, `Ламель` and contain subfolders `No Logo`, `WoodWay`, `Шпон в Україні`.
* Brand resources appear under `WoodWay`/`WW`, `Шпон в Україні`, `Байкал`/`Baykal`.

Based on this structure the search utilities apply the following rules:

- **Board images by default** – any path containing stock keywords is skipped unless the user explicitly requests stock photos (`stock`, `сток`, `склад`).
- **Brand handling** – queries containing brand identifiers (`woodway`, `ww`, `baykal`, `шпон`) surface images from those folders first and allow logo images.
- **Synonym and transliteration support** – both the original tokens and their ASCII transliterations are indexed. A small synonym map helps match English species names (``oak`` → ``дуб`` etc.).
- **Material synonyms** – common material types such as ``board``/``щит`` or ``veneer``/``шпон`` are also mapped to ensure queries in different languages return the same images.
- **Logo filtering** – non‑brand queries ignore files whose path includes `logo`.

These heuristics keep results focused on relevant board photos while still allowing branded or stock content when explicitly requested.
