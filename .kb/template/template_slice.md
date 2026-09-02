Implement only Slice `<slice_number>` for `<system_or_component>`.

First, read and follow:
- `AGENTS.md`
- `<product_documentation_path>`
- `<architecture_documentation_path>`

Task:
Implement the minimum working vertical slice for "`<capability>`".

Scope:
- create the minimal code needed to support `<primary_operation>` through `<interface>`
- persist `<entity_or_result>` using `<persistence_mechanism>`
- validate required fields and allowed values
- initialize or migrate the persistence schema if needed
- add automated tests for the implemented behavior

Expected behavior:
- `<interface_or_command>` accepts:
  - `<input_field_1>`
  - `<input_field_2>`
  - `<input_field_3>`
  - `<input_field_4>`
  - `<input_field_5>`
- new `<entities_or_results>` start with `<initial_state>`
- new `<entities_or_results>` have `<initial_optional_field>` = `<initial_value>`
- data is persisted using `<persistence_mechanism>`
- invalid input fails with a readable error

Constraints:
- do not implement `<out_of_scope_feature_1>`, `<out_of_scope_feature_2>`, `<out_of_scope_feature_3>`, or `<out_of_scope_feature_4>` yet
- do not add `<excluded_interface_or_infrastructure>`
- do not add `<excluded_dependency_or_abstraction>`
- keep `<layer_1>`, `<layer_2>`, `<layer_3>`, and `<layer_4>` separated
- keep the implementation small and readable
- use only runtime dependencies allowed by the project
- tests must run with `<canonical_test_command>`

Done when:
- Slice `<slice_number>` behavior is implemented
- relevant tests exist
- `<canonical_test_command>` passes
- no out-of-scope feature was added

Before coding:
1. briefly state the files you plan to touch
2. then implement
3. then run tests
4. then summarize what was added