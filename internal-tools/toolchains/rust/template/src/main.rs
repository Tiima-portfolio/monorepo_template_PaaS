/// Returns the service's greeting for `name`.
pub fn greeting(name: &str) -> String {
    format!("Hello from __NAME__, {name}")
}

fn main() {
    println!("{}", greeting("world"));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn greets_by_name() {
        assert_eq!(greeting("Ada"), "Hello from __NAME__, Ada");
    }
}
