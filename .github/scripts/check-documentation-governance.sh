#!/usr/bin/env bash

set -euo pipefail

base_revision="${1:-}"
head_revision="${2:-HEAD}"

if [[ -z "${base_revision}" ]]; then
  echo "Usage: $0 <base-revision> [head-revision]" >&2
  exit 2
fi

if ! changed_output="$(
  git diff --name-only --diff-filter=ACMR "${base_revision}" "${head_revision}"
)"; then
  echo "Documentation governance check could not inspect the requested revisions." >&2
  exit 2
fi

mapfile -t changed_files < <(printf '%s' "${changed_output}")

implementation_changed=false
task_documents=()

for file in "${changed_files[@]}"; do
  case "${file}" in
    AGENTS.md | */AGENTS.md)
      ;;
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

legacy_headings=(
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

current_headings=(
  "## 1. Overview"
  "## 2. Scope"
  "## 3. Prerequisites"
  "## 4. Architecture"
  "## 5. Step-by-Step Implementation Walkthrough"
  "## 6. Inputs"
  "## 7. Outputs"
  "## 8. Rules and Semantics"
  "## 9. Public Interfaces"
  "## 10. Data Ownership"
  "## 11. Security"
  "## 12. Error and Edge-Case Behavior"
  "## 13. Testing"
  "## 14. Verification"
  "## 15. Known Limitations"
  "## 16. Follow-Up Tasks"
  "## 17. References and Evidence"
)

validation_failed=false

for document in "${task_documents[@]}"; do
  required_headings=("${current_headings[@]}")
  # Only documents already present at the base revision may use the original format.
  # The legacy marker selects a full validation, not an exemption from any headings.
  if git cat-file -e "${base_revision}:${document}" 2>/dev/null &&
    grep -Fqx "## 5. Inputs" "${document}"; then
    required_headings=("${legacy_headings[@]}")
  fi

  for heading in "${required_headings[@]}"; do
    if ! grep -Fqx "${heading}" "${document}"; then
      echo "${document}: missing required heading: ${heading}" >&2
      validation_failed=true
    fi
  done

  # Compare all section headings to reject duplicates, reordering, and mixed formats.
  actual_headings="$(grep '^## ' "${document}" || true)"
  expected_headings="$(printf '%s\n' "${required_headings[@]}")"
  if [[ "${actual_headings}" != "${expected_headings}" ]]; then
    echo "${document}: section headings must match the complete ${#required_headings[@]}-section format in order." >&2
    validation_failed=true
  fi
done

if [[ "${validation_failed}" == true ]]; then
  echo "Task documents must follow docs/templates/TASK_DOCUMENTATION_TEMPLATE.md; existing documents may retain the complete original 16-section format." >&2
  exit 1
fi

echo "Documentation governance check passed."
