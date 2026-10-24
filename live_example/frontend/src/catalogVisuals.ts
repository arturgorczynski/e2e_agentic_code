// Generated visuals are illustrative. SKU concepts match catalog descriptions;
// neither these nor category images are verified photographs of stocked goods.
const skuConcepts: Record<string, string> = {
  'UCI-SKU-85123A': '/images/sku-85123a-concept.webp',
  'UCI-SKU-22384': '/images/sku-22384-concept.webp',
  'UCI-SKU-22386': '/images/sku-22386-concept.webp',
  'UCI-SKU-22423': '/images/sku-22423-concept.webp',
  'UCI-SKU-72800B': '/images/sku-72800b.webp',
  'UCI-SKU-23437': '/images/sku-23437.webp',
  'UCI-SKU-23345': '/images/sku-23345.webp',
  'UCI-SKU-23391': '/images/sku-23391.webp',
  'UCI-SKU-23472': '/images/sku-23472-concept.png',
  'UCI-SKU-23438': '/images/sku-23438-concept.png',
  'UCI-SKU-85099B': '/images/sku-85099b-concept.webp',
  'UCI-SKU-47566': '/images/sku-47566-concept.webp',
  'UCI-SKU-84879': '/images/sku-84879-concept.webp',
  'UCI-SKU-20725': '/images/sku-20725-concept.webp',
  'UCI-SKU-22720': '/images/sku-22720-concept.webp',
  'UCI-SKU-22457': '/images/sku-22457-concept.webp',
  'UCI-SKU-22469': '/images/sku-22469-concept.webp',
  'UCI-SKU-22178': '/images/sku-22178-concept.webp',
  'UCI-SKU-23203': '/images/sku-23203-concept.webp',
  'UCI-SKU-23298': '/images/sku-23298-concept.webp',
  'UCI-SKU-22197': '/images/sku-22197-concept.webp',
  'UCI-SKU-22086': '/images/sku-22086-concept.webp',
  'UCI-SKU-23209': '/images/sku-23209-concept.webp',
  'UCI-SKU-21212': '/images/sku-21212-concept.webp',
  'UCI-SKU-22960': '/images/sku-22960-concept.webp',
  'UCI-SKU-22624': '/images/sku-22624-concept.webp',
  'UCI-SKU-22697': '/images/sku-22697-concept.webp',
  'UCI-SKU-22699': '/images/sku-22699-concept.webp',
  'UCI-SKU-82482': '/images/sku-82482-concept.webp',
  'UCI-SKU-22727': '/images/sku-22727-concept.webp',
  'UCI-SKU-22726': '/images/sku-22726-concept.webp',
  'UCI-SKU-22993': '/images/sku-22993-concept.webp',
  'UCI-SKU-20727': '/images/sku-20727-concept.webp',
  'UCI-SKU-20728': '/images/sku-20728-concept.webp',
  'UCI-SKU-22666': '/images/sku-22666-concept.webp',
  'UCI-SKU-84946': '/images/sku-84946-concept.webp',
  'UCI-SKU-23084': '/images/sku-23084-concept.webp',
  'UCI-SKU-21790': '/images/sku-21790-concept.webp',
  'UCI-SKU-22138': '/images/sku-22138-concept.png',
  'UCI-SKU-22112': '/images/sku-22112-concept.png',
  'UCI-SKU-23245': '/images/sku-23245-concept.webp',
  'UCI-SKU-22382': '/images/sku-22382-concept.webp',
  'UCI-SKU-22139': '/images/sku-22139-concept.webp',
  'UCI-SKU-22411': '/images/sku-22411-concept.webp',
  'UCI-SKU-20914': '/images/sku-20914-concept.webp',
  'UCI-SKU-22383': '/images/sku-22383-concept.webp',
  'UCI-SKU-21754': '/images/sku-21754-concept.webp',
  'UCI-SKU-22722': '/images/sku-22722-concept.webp',
  'UCI-SKU-23301': '/images/sku-23301-concept.webp',
  'UCI-SKU-22961': '/images/sku-22961-concept.webp',
  'UCI-SKU-23206': '/images/sku-23206-concept.webp',
  'UCI-SKU-82494L': '/images/sku-82494l-concept.webp',
  'UCI-SKU-23201': '/images/sku-23201-concept.webp',
  'UCI-SKU-23202': '/images/sku-23202-concept.webp',
  'UCI-SKU-82484': '/images/sku-82484-concept.webp',
  'SCN-SKU-75F3A546B17E': '/images/modern-winter-garland.png',
  'SCN-SKU-79511D9988BA': '/images/modern-linen-notebook.png',
  'SCN-SKU-83DAA020DE34': '/images/modern-homewares-pack.png',
  'SCN-SKU-915D2A47B86E': '/images/modern-stoneware-cup.png',
  'SCN-SKU-A12C4F10C352': '/images/modern-amber-holder.png',
  'SCN-SKU-E82C3F1A2789': '/images/modern-cotton-towels.png',
  'SCN-SKU-F57045351520': '/images/modern-homewares-pack.png',
  'SCN-SKU-F909BB661742': '/images/modern-winter-garland.png',
}

const categoryImages: Record<string, string> = {
  'Lighting and candles': '/images/candles-assortment.webp',
  'Kitchen and tableware': '/images/kitchen-assortment.webp',
  'Seasonal decorations': '/images/seasonal-assortment.webp',
  'Stationery': '/images/stationery-assortment.webp',
  'Packaging and storage': '/images/packaging-assortment.webp',
  'Textiles': '/images/textiles-assortment.webp',
  'Home and gift accessories': '/images/home-assortment.webp',
}

export function categoryImage(category: unknown, productId?: unknown): string | undefined {
  return skuConcepts[String(productId)] ?? categoryImages[String(category)]
}

export function productImageLabel(productId: unknown, category: unknown): string {
  if (skuConcepts[String(productId)]) return 'AI concept · illustrative'
  return categoryImages[String(category)] ? 'Category image · illustrative' : 'No image available'
}

export function productImageAlt(productId: unknown, category: unknown, name: unknown): string {
  return skuConcepts[String(productId)]
    ? `Illustrative concept for ${String(name)}; appearance of actual stock is unverified`
    : `Illustrative ${String(category)} assortment; individual item may differ`
}
