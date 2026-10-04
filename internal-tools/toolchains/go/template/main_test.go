package main

import "testing"

func TestGreeting(t *testing.T) {
	if got, want := Greeting("Ada"), "Hello from __NAME__, Ada"; got != want {
		t.Fatalf("Greeting() = %q, want %q", got, want)
	}
}
