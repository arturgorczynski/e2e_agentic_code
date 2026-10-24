# Dataset attribution and redistribution

The UCI-derived prepared data is adapted from:

Chen, D. (2015). **Online Retail** [Dataset]. UCI Machine Learning Repository.
DOI: https://doi.org/10.24432/C5BW33
Source: https://archive.ics.uci.edu/dataset/352/online%2Bretail
License: **Creative Commons Attribution 4.0 International (CC BY 4.0)**,
https://creativecommons.org/licenses/by/4.0/

The dataset page permits sharing and adaptation with appropriate credit. Keep this
attribution, the source/license links, and an indication of changes with redistributed
prepared data. No endorsement by the creator or UCI is implied. The license applies
to the source-derived data; it is not a declaration of a license for unrelated project
code, generated identities, or future third-party assets.

Changes in `uci-retail-v1`: conversion from XLSX to UTF-8 compressed CSV, explicit
row identities, ISO local timestamps, decimal-string prices, duplicate/quality flags,
per-invoice eligibility and group summaries, and a reproducible measured profile.
All source rows and invoice groups are retained. No observed customer identities are
invented and no source transaction dates are shifted.

Microsoft Wide World Importers is cited as an architectural reference only:
https://learn.microsoft.com/en-us/sql/samples/wide-world-importers-what-is?view=sql-server-ver17
Its sample repository identifies an MIT license at
https://github.com/microsoft/sql-server-samples/blob/master/license.txt
No WWI code, database rows, backups, images or document text are bundled. Any future
asset reuse requires checking the asset's own notices and retaining applicable terms.
