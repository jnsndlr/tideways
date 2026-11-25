# Each invocation checks one Godot process. Some engine failures exit zero.
{ gsub(/\033\[[0-9;]*m/, ""); sub(/\r$/, "") }
/^TEST PASSED$/ { completed = 1 }
/^[[:space:]]*WARNING: .*ObjectDB instances? .*leaked at exit/ { failed = 1 }
# This test deliberately loads a scene whose external dependency is missing.
phase == "region-load-recovery" {
  if ($0 ~ /^ERROR: Cannot open file \047user:\/\/region_part_[0-9]+\.tscn\047\.$/ ||
      $0 ~ /^ERROR: Failed loading resource: user:\/\/region_(part|retry)_[0-9]+\.tscn\.$/ ||
      $0 ~ /^ERROR: user:\/\/region_retry_[0-9]+\.tscn:3 - Parse Error: \[ext_resource\] referenced non-existent resource at: user:\/\/region_part_[0-9]+\.tscn\.$/) next
}
/^[[:space:]]*(SCRIPT ERROR|ERROR):/ { failed = 1 }
END {
  if (expected == "test" && !completed) {
    print phase " ended without a test pass marker." > "/dev/stderr"
    failed = 1
  }
  exit failed ? 1 : 0
}
