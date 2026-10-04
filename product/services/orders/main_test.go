package main

import "testing"

func TestGreeting(t *testing.T) {
	if got, want := Greeting("Ada"), "Hello from orders, Ada"; got != want {
		t.Fatalf("Greeting() = %q, want %q", got, want)
	}
}

func TestGreetingWithoutName(t *testing.T) {
	if got, want := Greeting("  "), "Hello from orders, guest"; got != want {
		t.Fatalf("Greeting() = %q, want %q", got, want)
	}
}
