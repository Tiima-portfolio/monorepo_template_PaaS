export interface Product {
  id: string;
  name: string;
  priceCents: number;
}

const PRODUCTS: readonly Product[] = [
  { id: 'p-1', name: 'Starter plan', priceCents: 0 },
  { id: 'p-2', name: 'Team plan', priceCents: 4900 },
];

// Products whose name contains the query, case-insensitively.
export function listProducts(query = ''): Product[] {
  const q = query.trim().toLowerCase();
  return PRODUCTS.filter((p) => p.name.toLowerCase().includes(q));
}
