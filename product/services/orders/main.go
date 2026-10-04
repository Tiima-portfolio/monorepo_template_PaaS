package main

import (
	"fmt"
	"strings"
)

// Greeting returns the service's greeting for name.
func Greeting(name string) string {
	if strings.TrimSpace(name) == "" {
		name = "guest"
	}
	return fmt.Sprintf("Hello from orders, %s", name)
}

func main() {
	fmt.Println(Greeting("world"))
}
