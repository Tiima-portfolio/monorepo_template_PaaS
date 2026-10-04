// Package catalog holds the orders service's consumer contract for catalog:
// the shape of catalog's product listing that orders relies on. products.json
// is the example payload; catalog's own tests run it against its real output.
package catalog

import (
	"encoding/json"
	"os"
	"testing"
)

// Product is the part of catalog's product that orders uses.
type Product struct {
	ID         string `json:"id"`
	Name       string `json:"name"`
	PriceCents int    `json:"priceCents"`
}

func TestProductListingShape(t *testing.T) {
	data, err := os.ReadFile("products.json")
	if err != nil {
		t.Fatal(err)
	}
	var products []Product
	if err := json.Unmarshal(data, &products); err != nil {
		t.Fatalf("catalog's listing no longer decodes: %v", err)
	}
	if len(products) == 0 {
		t.Fatal("orders needs at least one product in the example listing")
	}
	for _, p := range products {
		if p.ID == "" || p.Name == "" || p.PriceCents < 0 {
			t.Errorf("product %+v breaks what orders relies on", p)
		}
	}
}
