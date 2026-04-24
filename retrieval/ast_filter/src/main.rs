use std::fs;
use std::io::{self, Read};
use std::path::Path;

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap_or(0);

    let request: serde_json::Value = match serde_json::from_str(&input) {
        Ok(v) => v,
        Err(_) => {
            println!("{{\"matches\":[]}}");
            return;
        }
    };

    let files: Vec<String> = request["files"]
        .as_array()
        .map(|a| {
            a.iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();

    let triggers = match request["triggers"].as_array() {
        Some(t) => t,
        None => {
            println!("{{\"matches\":[]}}");
            return;
        }
    };

    // Read each file once, store contents keyed by path.
    let mut file_contents: Vec<(String, String)> = Vec::with_capacity(files.len());
    for file_path in &files {
        let p = Path::new(file_path);
        if !p.exists() {
            continue;
        }
        if let Ok(content) = fs::read_to_string(p) {
            file_contents.push((file_path.clone(), content));
        }
    }

    let mut matches: Vec<serde_json::Value> = Vec::new();

    for trigger in triggers {
        let constraint_id = trigger["constraint_id"].as_str().unwrap_or("");
        let patterns: Vec<&str> = trigger["patterns"]
            .as_array()
            .map(|a| a.iter().filter_map(|v| v.as_str()).collect())
            .unwrap_or_default();

        if patterns.is_empty() {
            continue;
        }

        let mut matched_patterns: Vec<&str> = Vec::new();
        let mut matched_files: Vec<&str> = Vec::new();

        for (path, content) in &file_contents {
            for pattern in &patterns {
                if content.contains(*pattern) {
                    if !matched_patterns.contains(pattern) {
                        matched_patterns.push(pattern);
                    }
                    let path_str = path.as_str();
                    if !matched_files.contains(&path_str) {
                        matched_files.push(path_str);
                    }
                }
            }
        }

        if !matched_patterns.is_empty() {
            matches.push(serde_json::json!({
                "constraint_id": constraint_id,
                "matched_patterns": matched_patterns,
                "matched_files": matched_files,
            }));
        }
    }

    let output = serde_json::json!({ "matches": matches });
    println!("{}", serde_json::to_string(&output).unwrap_or_else(|_| "{\"matches\":[]}".to_string()));
}
