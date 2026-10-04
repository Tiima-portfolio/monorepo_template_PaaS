package main

import "fmt"

// Greeting returns the service's greeting for name.
func Greeting(name string) string {
	return fmt.Sprintf("Hello from orders, %s", name)
}

func main() {
	fmt.Println(Greeting("world"))
}
