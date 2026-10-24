# Catalog image notes

Fifty-five featured historical-SKU concepts were generated for this fictional catalog on
2026-10-20 through 2026-10-22 with the built-in `imagegen` tool. Fifty-one were encoded as WebP; four are
project-local PNG files. They are
**illustrative AI concepts based on source descriptions**, not photographs of
the actual stock. The website labels them accordingly. All other product cards
use category assortment images and are labeled separately. Six additional
concepts cover all eight contemporary scenario SKUs; the two pairs of SKUs
with identical generic descriptions share a concept image. These are also
illustrative and do not establish the appearance of any physical stock.

The read-only [catalog image audit](../scripts/audit_catalog_images.py) checks
every SKU and category mapping, image signature, mapped product and category
against `state/company.sqlite`, and byte counts, hashes and descriptions in
available per-asset manifests. Run it after preparing the exercise database:

```powershell
.\.venv\Scripts\python.exe -m scripts.audit_catalog_images
```

The [22 October inventory](../artifacts/catalog-image-audit-2026-10-22-r2.json)
found 63 mapped SKU images (55 historical and eight contemporary), seven
category images and no broken links or mismatches. It records the database
description and current file hash for each SKU. Forty-one SKU images have a
detailed per-asset generation manifest. The other 22 are identified explicitly
in the audit as older mappings without one; a current file hash verifies their
bytes but does not reconstruct an original generation prompt or source file.

| Product ID | Description in SQLite | Website asset |
| --- | --- | --- |
| `UCI-SKU-85123A` | WHITE HANGING HEART T-LIGHT HOLDER | [`sku-85123a-concept.webp`](../frontend/public/images/sku-85123a-concept.webp) |
| `UCI-SKU-22423` | REGENCY CAKESTAND 3 TIER | [`sku-22423-concept.webp`](../frontend/public/images/sku-22423-concept.webp) |
| `UCI-SKU-22384` | LUNCH BAG PINK POLKADOT | [`sku-22384-concept.webp`](../frontend/public/images/sku-22384-concept.webp) |
| `UCI-SKU-22386` | JUMBO BAG PINK POLKADOT | [`sku-22386-concept.webp`](../frontend/public/images/sku-22386-concept.webp) |
| `UCI-SKU-72800B` | 4 PURPLE FLOCK DINNER CANDLES | [`sku-72800b.webp`](../frontend/public/images/sku-72800b.webp) |
| `UCI-SKU-23437` | 50'S CHRISTMAS GIFT BAG LARGE | [`sku-23437.webp`](../frontend/public/images/sku-23437.webp) |
| `UCI-SKU-23345` | DOLLY GIRL BEAKER | [`sku-23345.webp`](../frontend/public/images/sku-23345.webp) |
| `UCI-SKU-23391` | I LOVE LONDON MINI BACKPACK | [`sku-23391.webp`](../frontend/public/images/sku-23391.webp) |
| `UCI-SKU-23472` | NINE DRAWER OFFICE TIDY | [`sku-23472-concept.png`](../frontend/public/images/sku-23472-concept.png) |
| `UCI-SKU-23438` | RED SPOT GIFT BAG LARGE | [`sku-23438-concept.png`](../frontend/public/images/sku-23438-concept.png) |
| `UCI-SKU-85099B` | JUMBO BAG RED RETROSPOT | [`sku-85099b-concept.webp`](../frontend/public/images/sku-85099b-concept.webp) |
| `UCI-SKU-47566` | PARTY BUNTING | [`sku-47566-concept.webp`](../frontend/public/images/sku-47566-concept.webp) |
| `UCI-SKU-84879` | ASSORTED COLOUR BIRD ORNAMENT | [`sku-84879-concept.webp`](../frontend/public/images/sku-84879-concept.webp) |
| `UCI-SKU-20725` | LUNCH BAG RED RETROSPOT | [`sku-20725-concept.webp`](../frontend/public/images/sku-20725-concept.webp) |
| `UCI-SKU-22720` | SET OF 3 CAKE TINS PANTRY DESIGN | [`sku-22720-concept.webp`](../frontend/public/images/sku-22720-concept.webp) |
| `UCI-SKU-22457` | NATURAL SLATE HEART CHALKBOARD | [`sku-22457-concept.webp`](../frontend/public/images/sku-22457-concept.webp) |
| `UCI-SKU-22469` | HEART OF WICKER SMALL | [`sku-22469-concept.webp`](../frontend/public/images/sku-22469-concept.webp) |
| `UCI-SKU-22178` | VICTORIAN GLASS HANGING T-LIGHT | [`sku-22178-concept.webp`](../frontend/public/images/sku-22178-concept.webp) |
| `UCI-SKU-23203` | JUMBO BAG DOILEY PATTERNS | [`sku-23203-concept.webp`](../frontend/public/images/sku-23203-concept.webp) |
| `UCI-SKU-23298` | SPOTTY BUNTING | [`sku-23298-concept.webp`](../frontend/public/images/sku-23298-concept.webp) |
| `UCI-SKU-22197` | SMALL POPCORN HOLDER | [`sku-22197-concept.webp`](../frontend/public/images/sku-22197-concept.webp) |
| `UCI-SKU-22086` | PAPER CHAIN KIT 50'S CHRISTMAS | [`sku-22086-concept.webp`](../frontend/public/images/sku-22086-concept.webp) |
| `UCI-SKU-23209` | LUNCH BAG DOILEY PATTERN | [`sku-23209-concept.webp`](../frontend/public/images/sku-23209-concept.webp) |
| `UCI-SKU-21212` | PACK OF 72 RETROSPOT CAKE CASES | [`sku-21212-concept.webp`](../frontend/public/images/sku-21212-concept.webp) |
| `UCI-SKU-22960` | JAM MAKING SET WITH JARS | [`sku-22960-concept.webp`](../frontend/public/images/sku-22960-concept.webp) |
| `UCI-SKU-22699` | ROSES REGENCY TEACUP AND SAUCER | [`sku-22699-concept.webp`](../frontend/public/images/sku-22699-concept.webp) |
| `UCI-SKU-22697` | GREEN REGENCY TEACUP AND SAUCER | [`sku-22697-concept.webp`](../frontend/public/images/sku-22697-concept.webp) |
| `UCI-SKU-22624` | IVORY KITCHEN SCALES | [`sku-22624-concept.webp`](../frontend/public/images/sku-22624-concept.webp) |
| `UCI-SKU-82482` | WOODEN PICTURE FRAME WHITE FINISH | [`sku-82482-concept.webp`](../frontend/public/images/sku-82482-concept.webp) |
| `UCI-SKU-22727` | ALARM CLOCK BAKELIKE RED | [`sku-22727-concept.webp`](../frontend/public/images/sku-22727-concept.webp) |
| `UCI-SKU-22726` | ALARM CLOCK BAKELIKE GREEN | [`sku-22726-concept.webp`](../frontend/public/images/sku-22726-concept.webp) |
| `UCI-SKU-22993` | SET OF 4 PANTRY JELLY MOULDS | [`sku-22993-concept.webp`](../frontend/public/images/sku-22993-concept.webp) |
| `UCI-SKU-20727` | LUNCH BAG BLACK SKULL | [`sku-20727-concept.webp`](../frontend/public/images/sku-20727-concept.webp) |
| `UCI-SKU-22666` | RECIPE BOX PANTRY YELLOW DESIGN | [`sku-22666-concept.webp`](../frontend/public/images/sku-22666-concept.webp) |
| `UCI-SKU-84946` | ANTIQUE SILVER TEA GLASS ETCHED | [`sku-84946-concept.webp`](../frontend/public/images/sku-84946-concept.webp) |
| `UCI-SKU-20728` | LUNCH BAG CARS BLUE | [`sku-20728-concept.webp`](../frontend/public/images/sku-20728-concept.webp) |
| `UCI-SKU-23084` | RABBIT NIGHT LIGHT | [`sku-23084-concept.webp`](../frontend/public/images/sku-23084-concept.webp) |
| `UCI-SKU-21790` | VINTAGE SNAP CARDS | [`sku-21790-concept.webp`](../frontend/public/images/sku-21790-concept.webp) |
| `UCI-SKU-22138` | BAKING SET 9 PIECE RETROSPOT | [`sku-22138-concept.png`](../frontend/public/images/sku-22138-concept.png) |
| `UCI-SKU-22112` | CHOCOLATE HOT WATER BOTTLE | [`sku-22112-concept.png`](../frontend/public/images/sku-22112-concept.png) |
| `UCI-SKU-23245` | SET OF 3 REGENCY CAKE TINS | [`sku-23245-concept.webp`](../frontend/public/images/sku-23245-concept.webp) |
| `UCI-SKU-22382` | LUNCH BAG SPACEBOY DESIGN | [`sku-22382-concept.webp`](../frontend/public/images/sku-22382-concept.webp) |
| `UCI-SKU-22139` | RETROSPOT TEA SET CERAMIC 11 PC | [`sku-22139-concept.webp`](../frontend/public/images/sku-22139-concept.webp) |
| `UCI-SKU-22411` | JUMBO SHOPPER VINTAGE RED PAISLEY | [`sku-22411-concept.webp`](../frontend/public/images/sku-22411-concept.webp) |
| `UCI-SKU-20914` | SET/5 RED RETROSPOT LID GLASS BOWLS | [`sku-20914-concept.webp`](../frontend/public/images/sku-20914-concept.webp) |
| `UCI-SKU-22383` | LUNCH BAG SUKI DESIGN | [`sku-22383-concept.webp`](../frontend/public/images/sku-22383-concept.webp) |
| `UCI-SKU-21754` | HOME BUILDING BLOCK WORD | [`sku-21754-concept.webp`](../frontend/public/images/sku-21754-concept.webp) |
| `UCI-SKU-22722` | SET OF 6 SPICE TINS PANTRY DESIGN | [`sku-22722-concept.webp`](../frontend/public/images/sku-22722-concept.webp) |
| `UCI-SKU-23301` | GARDENERS KNEELING PAD KEEP CALM | [`sku-23301-concept.webp`](../frontend/public/images/sku-23301-concept.webp) |
| `UCI-SKU-22961` | JAM MAKING SET PRINTED | [`sku-22961-concept.webp`](../frontend/public/images/sku-22961-concept.webp) |
| `UCI-SKU-23206` | LUNCH BAG APPLE DESIGN | [`sku-23206-concept.webp`](../frontend/public/images/sku-23206-concept.webp) |
| `UCI-SKU-82494L` | WOODEN FRAME ANTIQUE WHITE | [`sku-82494l-concept.webp`](../frontend/public/images/sku-82494l-concept.webp) |
| `UCI-SKU-23201` | JUMBO BAG ALPHABET | [`sku-23201-concept.webp`](../frontend/public/images/sku-23201-concept.webp) |
| `UCI-SKU-23202` | JUMBO BAG VINTAGE LEAF | [`sku-23202-concept.webp`](../frontend/public/images/sku-23202-concept.webp) |
| `UCI-SKU-82484` | WOOD BLACK BOARD ANT WHITE FINISH | [`sku-82484-concept.webp`](../frontend/public/images/sku-82484-concept.webp) |
| `SCN-SKU-79511D9988BA` | Linen-cover desk notebook | [`modern-linen-notebook.png`](../frontend/public/images/modern-linen-notebook.png) |
| `SCN-SKU-915D2A47B86E` | Ivory stoneware breakfast cup | [`modern-stoneware-cup.png`](../frontend/public/images/modern-stoneware-cup.png) |
| `SCN-SKU-A12C4F10C352` | Amber glass candle holder | [`modern-amber-holder.png`](../frontend/public/images/modern-amber-holder.png) |
| `SCN-SKU-E82C3F1A2789` | Cotton tea towel pair | [`modern-cotton-towels.png`](../frontend/public/images/modern-cotton-towels.png) |
| `SCN-SKU-75F3A546B17E`, `SCN-SKU-F909BB661742` | Winter garland display set | [`modern-winter-garland.png`](../frontend/public/images/modern-winter-garland.png) |
| `SCN-SKU-83DAA020DE34`, `SCN-SKU-F57045351520` | Assorted homewares pack | [`modern-homewares-pack.png`](../frontend/public/images/modern-homewares-pack.png) |

The image map is in [`catalogVisuals.ts`](../frontend/src/catalogVisuals.ts).
The r16 additions cover 642 and 618 distinct non-cancelled
source-derived orders respectively in the active exercise database. Their
printed jam-kit contents and apple fabric pattern are invented interpretations
of short stock descriptions. The [r16 asset manifest](../artifacts/image-assets-2026-10-22-r16.json)
records the exact prompts, generated originals, dimensions and hashes.
Two more source descriptions that previously used category images now have
individual concepts: `UCI-SKU-82494L` (antique-white wooden frame, 604 distinct
non-cancelled orders) and `UCI-SKU-23201` (alphabet jumbo bag, 598). The frame's
distressed paint and the bag's colors, print and fabric are invented visual
choices. Their names and order counts come from the local SQLite catalog and
order history, not from photographs. Both files were visually reviewed and
encoded as WebP; the [r17 manifest](../artifacts/image-assets-2026-10-22-r17.json)
records the exact prompts, source PNG paths, dimensions and SHA-256 hashes.

Two further concepts add a vintage-leaf jumbo bag (`UCI-SKU-23202`, 585
distinct non-cancelled source orders) and an antique-white framed blackboard
(`UCI-SKU-82484`, 481). Their leaf print, fabric, finish and easel shape are
invented visual choices. The source descriptions and order counts were read
from the active SQLite history. Both outputs were visually inspected and
converted to WebP; the [r18 manifest](../artifacts/image-assets-2026-10-22-r18.json)
records the prompts, source PNGs, dimensions and hashes.

Four earlier concepts cover a lunch bag (727 distinct non-cancelled source
orders), HOME display blocks (515), a six-tin pantry set (490) and a gardener's
kneeling pad (515). The active SQLite names and order counts guided selection.
Original prints, lettering treatment, materials, tin artwork and pad shape are
invented. A generic [kneeling-pad product example](https://www.homewareessentials.co.uk/marksman-kneeling-pad)
helped check that the illustrated object reads as a portable pad; its photograph
was not copied. Prompts, generated-file paths, dimensions and WebP hashes are
recorded in [`image-assets-2026-10-21-r13.json`](../artifacts/image-assets-2026-10-21-r13.json).
The preceding two concepts cover a large red paisley shopper (`UCI-SKU-22411`,
600 distinct non-cancelled source orders) and five lidded glass bowls
(`UCI-SKU-20914`, 519). Their counts and descriptions were checked against
the active SQLite history on 21 October 2026. The tote material, paisley
layout and bowl-lid construction are visual inventions. Exact prompts,
source image paths, dimensions and WebP hashes are in
[`image-assets-2026-10-21-r12.json`](../artifacts/image-assets-2026-10-21-r12.json).
The original generated PNG files remain in the imagegen output directory;
the website uses project-local copies. To add an image for a
new stock code, add an explicit ID mapping. A category match alone must not be
labeled as an individual product concept.

The preceding pair of concepts covers a nine-piece Retrospot baking set (585 distinct
non-cancelled source-derived orders) and a chocolate hot-water bottle (548),
using the live exercise database checked on 2026-10-21. The source gives only
the product names: the set's exact contents, materials and polka-dot layout,
and the bottle's knitted cover are invented visual choices. Their prompts and
checksums are recorded in
[`image-assets-2026-10-21-r8.json`](../artifacts/image-assets-2026-10-21-r8.json).

An earlier group of three historical concepts was chosen from the active
source-derived order history because they were frequently ordered but still
showed category assortments: `UCI-SKU-20725` appears in 935 distinct
non-cancelled orders, `UCI-SKU-22720` in 858, and `UCI-SKU-22457` in 764
(checked against `state/company.sqlite` on 2026-10-20). These counts rank
the image work; they do not establish product appearance. The source
descriptions above were the only product-specific visual evidence used for
their prompts.

The three 2026-10-21 additions were also selected by observed activity:
`UCI-SKU-23203` occurred in 839 non-cancelled orders, `UCI-SKU-22469` in
732, and `UCI-SKU-22178` in 676. Their exact historical appearance is
unknown; the image map continues to label each as an AI concept.

Three further 2026-10-21 concepts cover `UCI-SKU-23298` (774 non-cancelled
orders), `UCI-SKU-22197` (726) and `UCI-SKU-22086` (703). These counts were
read from the active SQLite order history and guided selection only. Their
source descriptions do not specify exact materials, packaging or colors; the
resulting images are plausible fictional concepts. The exact prompts, output
dimensions and WebP hashes are in
[`image-assets-2026-10-21-r2.json`](../artifacts/image-assets-2026-10-21-r2.json).

Four further concepts cover the most frequently ordered unillustrated lunch
bag (`UCI-SKU-23209`, 767 non-cancelled orders), plus distinct cake-case
(`UCI-SKU-21212`, 701), jam-making (`UCI-SKU-22960`, 669) and teacup
(`UCI-SKU-22699`, 638) product types. The counts and trimmed source
descriptions were checked against the active SQLite order history on 21 October
2026. The image for the jam-making set depicts possible contents, not a verified
list of the historical kit's parts. The exact prompts, source PNG names, WebP
hashes and dimensions are in
[`image-assets-2026-10-21-r3.json`](../artifacts/image-assets-2026-10-21-r3.json).

The next three concepts add distinct product forms: white wooden picture frame
(`UCI-SKU-82482`, 658 non-cancelled source orders), four jelly moulds
(`UCI-SKU-22993`, 626) and a red Bakelike alarm clock (`UCI-SKU-22727`, 625).
Their descriptions, activity counts and output hashes are recorded in
[`image-assets-2026-10-21-r4.json`](../artifacts/image-assets-2026-10-21-r4.json).
The generated frame size, clock mechanism and mould material are creative
choices, not claims about the physical 2011 items.

Three additional concepts cover a blue cars lunch bag (`UCI-SKU-20728`, 699
non-cancelled source orders), a rabbit night light (`UCI-SKU-23084`, 512) and
vintage snap cards (`UCI-SKU-21790`, 550). Their product forms follow the
source descriptions; the bag pattern, lamp construction and card artwork are
fictional. The exact selected stock codes, generation prompts, image dimensions
and WebP hashes are in
[`image-assets-2026-10-21-r6.json`](../artifacts/image-assets-2026-10-21-r6.json).

Three more concepts cover an unillustrated black skull lunch bag (757
non-cancelled source orders), an etched tea glass (578) and a yellow pantry
recipe box (569). Their forms come from the source descriptions; materials,
pattern details and dimensions remain fictional. The exact assets, source
descriptions, prompts and checksums are recorded in
[`image-assets-2026-10-21-r5.json`](../artifacts/image-assets-2026-10-21-r5.json).

## Generation prompt set

The historical prompts used the `product-mockup` use case, square catalog framing,
warm neutral studio tabletop, soft editorial lighting, no people, logos,
readable text or watermarks. The product subjects were:

1. **Candles:** “A set of FOUR purple flock dinner candles, tall slim tapers
   with velvety plum-purple surface, grouped upright in a simple unbranded
   kraft presentation sleeve with some candles visible. One clearly
   identifiable product, not a category assortment.”
2. **Gift bag:** “ONE large 1950s-inspired Christmas gift bag, retro
   mid-century holiday pattern in muted red, forest green and cream, sturdy
   paper handles, standing upright. Realistic paper texture; not a category
   assortment.”
3. **Beaker:** “ONE cheerful Dolly Girl beaker, a small durable child-friendly
   drinking cup with a playful illustrated doll motif in soft pink, teal and
   cream. Realistic ceramic or melamine texture; not a category assortment.”
4. **Backpack:** “ONE compact children's mini backpack inspired by London
   travel motifs, navy and red canvas with subtle stylized bus and landmark
   icons, visible zip and shoulder straps. Realistic textile detail; not a
   category assortment.”

5. **Office tidy:** A compact desktop organiser with exactly nine small drawers
   in a three-by-three arrangement, pale wood finish, blank pulls, no labels or
   extra stationery, on a warm cream studio background.
6. **Red spot bag:** One large upright cream paper gift bag with evenly spaced
   red spots, visible side gusset and twisted handles, without text, ribbon or
   other products, on a neutral studio background.

7. **Hanging heart holder:** One small white heart-shaped metal tealight holder,
   empty cup visible, suspended by a simple loop, matte enamel, three-quarter
   view on a warm neutral studio background.
8. **Regency cake stand:** One empty three-tier stand with three graduated cream
   ceramic plates and a central metal spindle, complete silhouette visible,
   traditional detailing and a neutral studio background.

9. **Red Retrospot jumbo bag:** One large reusable cream shopping tote with
   bold red polka dots, two handles and a visible side gusset, standing alone
   on a warm neutral studio tabletop.
10. **Party bunting:** One gently draped strand of triangular pennants in
    muted red, blue, yellow and cream, with the connecting cord visible against
    a warm neutral wall.
11. **Bird ornament assortment:** Three small hanging bird-shaped ornaments in
    muted teal, coral and ochre, suspended by loops from a simple branch in a
    neutral studio setting.
12. **Red Retrospot lunch bag:** One small boxy reusable lunch bag, distinct
    from the jumbo shopping tote, short handles, cream surface with evenly
    spaced red dots and visible side depth on a cream tabletop.
13. **Pantry cake tins:** Exactly three lidded round metal cake-storage tins
    in graduated sizes, grouped with all lids visible, muted cream, dusty red
    and slate blue vintage decoration without readable words.
14. **Slate heart chalkboard:** One blank, dark heart-shaped natural slate
    board with irregular cut edges and a simple jute hanging cord, leaning
    upright on a warm neutral tabletop.
15. **Small wicker heart:** Exactly one palm-sized hand-woven natural wicker
    heart with visible interlaced cane texture and an unobtrusive hanging loop,
    three-quarter view on warm ivory.
16. **Victorian glass tealight holder:** Exactly one small clear ribbed glass
    hanging holder with restrained antique silver-toned rim, three fine chains
    and a visible empty tealight cup, unlit, full silhouette in frame.
17. **Doily jumbo bag:** Exactly one large upright reusable tote, two handles
    and a side gusset, with a repeating white paper-doily-inspired print on
    muted charcoal and cream; the pattern is printed, not attached lace.
18. **Spotty bunting:** One draped strand of spotted triangular fabric pennants
    in muted red, dusty blue and cream, with the joining cord visible.
19. **Small popcorn holder:** One compact, empty, open-top paperboard snack
    carton with a scalloped rim and muted red-and-cream stripes, not a large
    cinema bucket.
20. **Christmas paper-chain kit:** One stack of pre-cut mid-century-style
    holiday paper strips beside a short assembled sample chain; abstract
    stars, snowflakes and dots, without text or branded characters.
21. **Doily lunch bag:** One compact reusable lunch bag with short handles,
    gusset and a printed cream-on-charcoal doily pattern, distinct from the
    already illustrated jumbo tote.
22. **Retrospot cake cases:** One pack of empty cream-and-red spotted fluted
    paper cake cases with several fanned out to show their shape.
23. **Jam-making set:** One fictional kit arrangement of three empty jars,
    a funnel and blank labels; the source name does not specify its contents.
24. **Roses teacup and saucer:** One matching cream ceramic pair with an
    original restrained rose motif, without copying a commercial pattern.
25. **White wooden picture frame:** One blank portrait frame with matte white
    painted wood and a visible easel stand. The source does not specify size.
26. **Red Bakelike alarm clock:** One original rounded red molded-case analog
    clock with small twin bells, cream face and no brand. The source names a
    Bakelite-like style, not verified material or exact construction.
27. **Four pantry jelly moulds:** Four separate empty fluted cups in muted
    pantry colors, with all hollow interiors visible. The source does not
    establish their material, size or color.

Every prompt requested centered composition and breathing room for both cards
and detail dialogs. The prompts guided generated *concepts*; they provide no
evidence of how historical stock actually looked.

The six contemporary prompts used the same `product-mockup` style and square
catalog framing. They described one linen notebook, one evergreen winter
garland set, one ivory stoneware cup, one empty amber glass holder, a matching
pair of cotton tea towels, and one compact homewares gift pack. All excluded
brands, readable text and watermarks. The duplicated generic SKU descriptions
reuse the matching concept rather than implying a difference that the database
does not record.

Two additional individually mapped concepts cover frequent historical source
items that still used category imagery: `UCI-SKU-22382` appeared in 666
distinct non-cancelled orders, and `UCI-SKU-22139` in 568. The first is a
fictional original space-print lunch bag. The second depicts a possible
eleven-piece ceramic set: one teapot, one sugar bowl, one milk jug, four cups
and four saucers. The source names the product and piece count, but does not
identify those exact components, colors or decoration. The selected images
were visually reviewed as product-specific concepts, and their exact prompts,
source PNG paths, WebP checksums and dimensions are recorded in
[`image-assets-2026-10-21-r11.json`](../artifacts/image-assets-2026-10-21-r11.json).
An unrelated [space-themed lunch bag listing](https://www.madeinbebe.com/boutique/fr/lunch-box-espace-a-little-lovely-company/a227887)
was consulted for the generic handle-and-zip product form. Its branded
pattern, stated materials and dimensions were not used as Acme stock facts
or copied into the generated image.

## Photo search and selection

We inspected real [ceramic product photographs on Unsplash](https://unsplash.com/photos/a-white-cup-sitting-on-top-of-a-table-UxBCLIPfu8Y)
and the [Unsplash](https://unsplash.com/license) and [Pexels](https://www.pexels.com/license/)
reuse terms. A real photograph of a similar cup does not establish that it is
the exact fictional Acme SKU. The featured assets therefore use
description-specific generated concepts, keep the visible illustrative label,
and are stored locally. Their generation prompts use product-mockup framing,
soft natural light and no brand, text, watermark, people or extra merchandise.
For the three added concepts, we also inspected examples of a
[white painted wooden frame](https://www.bunnings.com.au/profile-elegant-deluxe-4x6-6x8-photo-frame-white_p1182395),
a [red twin-bell alarm clock](https://www.1001pendules.fr/reveil-silencieux-rouge-en-metal-sonnerie-sur-cloche-_r_358_i_7240.html)
and [four small jelly moulds](https://item.rakuten.co.jp/livingut/333513/)
to check basic object form. Those listings were not copied into the app and
do not identify the 2011 source stock. The local concept choices and hashes
are recorded in [image-assets-2026-10-21-r4.json](../artifacts/image-assets-2026-10-21-r4.json).
The built-in `imagegen` tool created them; the selected historical assets were
copied or converted into project-local files for the website.

For the 2026-10-21 additions, generic [wicker-heart](https://www.truffaut.com/objet-deco-osier-d-12-cm-1.html)
and [hanging-glass-holder](https://www.fischers-lagerhaus.de/12358/teelichthalter-glas-haengend-oe-13-cm-h-16-cm)
product references helped check plausible materials and form. No supplier
photograph was copied. The doily bag concept was guided by the source
description alone. All three were generated as square `product-mockup`
images, visually reviewed, then encoded as project-local WebP assets.
The exact three prompts, file hashes and dimensions are recorded in
[`image-assets-2026-10-21.json`](../artifacts/image-assets-2026-10-21.json).

Three additional concepts now cover products that previously showed only
category assortments: the pink polka-dot lunch bag appeared in **688**
distinct non-cancelled source-derived orders, the green Regency teacup and
saucer in **569**, and ivory kitchen scales in **441**. Those are local order
counts, not evidence of actual product appearance. The bag's flap and fabric,
the cup's decorative band, and the scale's mechanical form were invented for
the concepts because the source descriptions do not specify them. The three
images were generated with built-in `image_gen` and encoded as local WebP
assets. Their prompts, output paths, dimensions and hashes are in
[`image-assets-2026-10-21-r9.json`](../artifacts/image-assets-2026-10-21-r9.json).
Three further concepts add a large pink polka-dot shopping tote (686 distinct
non-cancelled source orders), a green Bakelike alarm clock (567) and a set of
three Regency cake tins (555). They help distinguish the jumbo tote from the
smaller lunch bag, the green clock from the red one, and this tin set from the
Pantry set already illustrated. The source descriptions establish those names
and order counts only; tote dimensions and fabric, clock construction and
the tins' decorative design are invented visual choices. The built-in
`image_gen` outputs were visually inspected and encoded as project-local
WebP files. Exact prompts, original output paths, dimensions and SHA-256
hashes are in [r10](../artifacts/image-assets-2026-10-21-r10.json).
For the later popcorn holder and paper-chain kit, a
[small popcorn carton](https://msk-ingredients.com/msk-1734-mini-popcorn-box-by-100percent-chef-100pk)
and a [retro paper-chain kit](https://theholidaybarn.com/products/retro-christmas-paper-chain-garland-kit)
were checked as general form references. No supplier photograph was copied or
treated as evidence of the 2011 Acme item. Spotty bunting was guided by its
source description and the established catalog style.
For the four r3 additions, current [cake-case examples](https://www.lakeland.co.uk/products/60-lakeland-polka-dot-cupcake-cases),
[jam-making supplies](https://www.lakeland.co.uk/collections/make-your-own)
and a [floral teacup form](https://www.wedgwood.com/en-ca/products/royal-albert-old-country-roses-teacup-and-saucer)
were checked as general shape references. No retailer photograph or pattern
was copied. The doily lunch bag was generated from the source description and
the existing catalog style.
