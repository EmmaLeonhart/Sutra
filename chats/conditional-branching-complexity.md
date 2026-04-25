# Conditional branching time complexity


**Human:**

Conditional branching time complexity (no loops)


**Claude:**

Conditional branching (if/else, switch) has **O(1)** time complexity.

Each branch executes a fixed set of operations regardless of input size -- the code just picks one path and runs it. No iteration means no growth relative to *n*.

```python
if x > 0:
 return "positive" # O(1)
elif x < 0:
 return "negative" # O(1)
else:
 return "zero" # O(1)
# Overall: O(1)
```

The number of branches doesn't change this -- even 100 `elif` clauses is still O(1), because only **one** branch executes per call.

The one caveat: if a branch *calls a function*, the overall complexity is whatever that function costs, not the branch itself.
