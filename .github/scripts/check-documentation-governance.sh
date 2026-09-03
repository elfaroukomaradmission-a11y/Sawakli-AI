#!/usr/bin/env bash

set -euo pipefail

base_revision="${1:-}"
head_revision="${2:-HEAD}"

if [[ -z "${base_revision}" ]]; then
  echo "Usage: $0 <base-revision> [head-revision]" >&2
  exit 2
fi

mapfile -t changed_files < <(
  git diff --name-only --diff-filter=ACMR "${base_revision}" "${head_revision}"
)

implementation_changed=false
task_documents=()

for file in "${changed_files[@]}"; do
  case "${file}" in
    apps/* | agent/* | api/* | connector/* | database/* | infrastructure/* | tests/* | ui/* | worker/* | docker-compose.yml)
      implementation_changed=true
      ;;
  esac

  if [[ "${file}" =~ ^docs/[^/]+/[A-Z][A-Z0-9]*-[0-9]+-[a-z0-9][a-z0-9-]*\.md$ ]]; then
    task_documents+=("${file}")
  fi
done

if [[ "${implementation_changed}" == true && ${#task_documents[@]} -eq 0 ]]; then
  cat >&2 <<'EOF'
Documentation governance check failed.

This pull request changes implementation files but does not add or update a task document matching:
  docs/<layer>/<TASK-ID>-<short-name>.md

Create or update the task document in this pull request. If this is a genuinely non-behavioral
maintenance change, a repository owner may apply the "documentation-exempt" pull request label.
EOF
  exit 1
fi

required_headings=(
  "## 1. Overview"
  "## 2. Scope"
  "## 3. Prerequisites"
  "## 4. Architecture"
  "## 5. Inputs"
  "## 6. Outputs"
  "## 7. Rules and Semantics"
  "## 8. Public Interfaces"
  "## 9. Data Ownership"
  "## 10. Security"
  "## 11. Error and Edge-Case Behavior"
  "## 12. Testing"
  "## 13. Verification"
  "## 14. Known Limitations"
  "## 15. Follow-Up Tasks"
  "## 16. References and Evidence"
)

validation_failed=false

for document in "${task_documents[@]}"; do
  for heading in "${required_headings[@]}"; do
    if ! grep -Fqx "${heading}" "${document}"; then
      echo "${document}: missing required heading: ${heading}" >&2
      validation_failed=true
    fi
  done
done

if [[ "${validation_failed}" == true ]]; then
  echo "Task documents must follow docs/templates/TASK_DOCUMENTATION_TEMPLATE.md." >&2
  exit 1
fi

echo "Documentation governance check passed."
